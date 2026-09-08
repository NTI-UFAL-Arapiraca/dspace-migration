import os
import re
import csv
import html as html_module
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from dspace_migration.access import determine_access_policy, write_access_policies
from dspace_migration.organization import (
    load_curso_mapping,
    resolve_collection_for_curso,
    get_saf_subpath,
    MAPPING_FILE,
)

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5440")
DB_NAME = os.getenv("DB_NAME", "biblioteca")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
SAF_BUNDLE_DIR = os.getenv("SAF_BUNDLE_DIR", "saf_bundle")
DEFAULT_DOCUMENT_LANGUAGE = "pt_BR"

DEFAULT_SQL_FILE = Path("sql/extract_metadata.sql")
if not DEFAULT_SQL_FILE.exists():
    # Fallback to path relative to project root
    project_root = Path(__file__).resolve().parent.parent.parent
    DEFAULT_SQL_FILE = project_root / "sql" / "extract_metadata.sql"


def connect_db():
    """Estabelece e retorna a conexão com o banco de dados PostgreSQL."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def fetch_data_from_db(sql_file):
    """Lê a consulta SQL de um arquivo e executa no PostgreSQL retornando um DataFrame Pandas."""
    sql_path = Path(sql_file)
    print(f"Lendo consulta SQL de: {sql_path}")
    with open(sql_path, "r", encoding="utf-8") as f:
        sql_query = f.read()

    print(f"Conectando ao banco de dados {DB_NAME} em {DB_HOST}:{DB_PORT}...")
    conn = connect_db()
    try:
        df = pd.read_sql_query(sql_query, conn)
        return df
    finally:
        conn.close()


def process_data(
    sql_file=None,
    saf_bundle_dir=SAF_BUNDLE_DIR,
    limit=None,
):
    if sql_file is None:
        sql_file = DEFAULT_SQL_FILE

    print("Iniciando o processamento dos dados de metadados...")
    # Remove o relatório legado: políticas de acesso agora seguem somente no
    # manifesto técnico do SAF e são aplicadas diretamente no DSpace.
    Path("embargoed_items.csv").unlink(missing_ok=True)

    sql_path = Path(sql_file)
    if not sql_path.exists():
        raise FileNotFoundError(f"Arquivo SQL não encontrado em '{sql_path}'.")

    df = fetch_data_from_db(sql_path)

    if limit is not None:
        limit = int(limit)
        print(f"Limitando o processamento a {limit} registros (modo teste)...")
        df = df.head(limit)

    print(f"Total de registros carregados: {df.shape[0]}")

    # 1. Limpeza de HTML
    print("Limpando tags HTML...")
    html_pattern = re.compile(r'<[^>]+>|&nbsp;', flags=re.IGNORECASE)

    html_cols = [
        'dc.title',
        'dc.description.abstract[pt]',
        'dc.description.abstract[en]',
        'dc.description.note',
        'dc.identifier.citation',
    ]

    def clean_html(val):
        if pd.isna(val):
            return val
        # Remove tags HTML, depois faz unescape de entidades (&amp; → &, &lt; → <, etc.)
        cleaned = html_pattern.sub('', str(val))
        cleaned = html_module.unescape(cleaned)
        # Colapsa quebras de linha (\r\n, \r, \n) e espaços redundantes em espaço único
        cleaned = re.sub(r'[\r\n]+', ' ', cleaned)
        cleaned = re.sub(r'[ \t]+', ' ', cleaned).strip()
        # Retorna None se o conteúdo ficou vazio após limpeza
        return cleaned if cleaned else None

    for col in html_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_html)

    # 1b. Deduplicação de abstract: se pt == en (mesmo texto), mantém só pt
    print("Deduplicando abstracts bilíngues...")
    pt_col = 'dc.description.abstract[pt]'
    en_col  = 'dc.description.abstract[en]'
    if pt_col in df.columns and en_col in df.columns:
        # Caso 1: conteúdo idêntico → mantém pt, remove en
        same_mask = (
            df[pt_col].notna() & df[en_col].notna()
            & (df[pt_col].str.strip() == df[en_col].str.strip())
        )
        df.loc[same_mask, en_col] = None
        n_same = same_mask.sum()
        if n_same:
            print(f"  {n_same} registros com resumo == abstract (duplicatas removidas do campo en)")

    # 2. Tratamento dc.title.alternative
    print("Tratando dc.title.alternative...")
    if 'dc.title.alternative' in df.columns:
        df['dc.title.alternative'] = df['dc.title.alternative'].apply(
            lambda x: None if pd.notna(x) and str(x).strip().lower() == "abstract" else x
        )

    # 3. Padronização de Datas
    print("Padronizando datas...")
    def standardize_date(val):
        if pd.isna(val):
            return val
        s = str(val).strip()
        if re.match(r'^\d{4}$', s):
            return f"{s}-01-01"
        return s

    if 'dc.date.issued' in df.columns:
        df['dc.date.issued'] = df['dc.date.issued'].apply(standardize_date)

    # O acervo desta migração é composto por documentos em português do Brasil.
    # O campo faz parte do registro Dublin Core padrão do DSpace.
    df['dc.language.iso'] = DEFAULT_DOCUMENT_LANGUAGE

    # 4. Triagem de Observações vs Citações vs Notas Internas (Provenance)
    print("Realizando triagem de Observações vs Citações vs Notas Internas...")
    provenance_keywords = re.compile(
        r'\b(restrito|restrição|embargo|liberação|sigilo|confidencial|acesso\s+restrito|'
        r'somente\s+admin|sem\s+autoriza[çc][aã]o|n[aã]o\s+autoriza[a-zçãõ]*|'
        r'autoriza[çc][aã]o\s+(pendente|negada)|solicitad[ao]\s+pela?\s+autor[ae])\b',
        flags=re.IGNORECASE,
    )
    citation_keywords = re.compile(
        r'\b(v\.|n\.|p\.|vol\.|issn|doi|http|https|editora|revista|anais|scielo)\b',
        flags=re.IGNORECASE,
    )

    # Garante que a coluna de provenance existe (admin-only no DSpace por padrão)
    if 'dc.description.provenance' not in df.columns:
        df['dc.description.provenance'] = None

    if 'dc.description.note' in df.columns and 'dc.identifier.citation' in df.columns:
        for idx, row in df.iterrows():
            note_val = row['dc.description.note']
            cit_val = row['dc.identifier.citation']

            # Usa o texto disponível (note tem prioridade pois citation é cópia do mesmo campo)
            text = None
            if pd.notna(note_val) and str(note_val).strip() != "":
                text = str(note_val)
            elif pd.notna(cit_val) and str(cit_val).strip() != "":
                text = str(cit_val)

            if text is None:
                continue

            if provenance_keywords.search(text):
                # Nota interna de restrição/embargo → campo admin-only no DSpace
                df.at[idx, 'dc.description.provenance'] = text
                df.at[idx, 'dc.description.note'] = None
                df.at[idx, 'dc.identifier.citation'] = None
            elif citation_keywords.search(text):
                df.at[idx, 'dc.identifier.citation'] = text
                df.at[idx, 'dc.description.note'] = None
            else:
                # Observação geral (inclusive notas de acervo): evita que a
                # cópia criada no SQL apareça simultaneamente como citação.
                df.at[idx, 'dc.description.note'] = text
                df.at[idx, 'dc.identifier.citation'] = None

    # 5. Identificação de itens embargados/restritos
    print("Identificando políticas de embargo/restrição...")
    access_policies = {}
    for row in df.to_dict(orient='records'):
        policy = determine_access_policy(
            row.get('data_limite_embargo'),
            row.get('autorizar_publicacao'),
        )
        access_policies[row['id_origem']] = policy
    protected_count = sum(policy is not None for policy in access_policies.values())
    print(
        f"Identificados {protected_count} itens embargados/restritos; "
        "as políticas serão aplicadas no DSpace."
    )

    # 6. Carregar mapeamento de cursos
    print("Carregando mapeamento de cursos (map.json)...")
    curso_mapping = load_curso_mapping(MAPPING_FILE)
    print(f"Mapeamento carregado: {len(curso_mapping)} cursos mapeados.")

    # Colunas de controle ou gerenciadas internamente pelo DSpace que não
    # devem ser escritas no dublin_core.xml.
    EXCLUDED_COLUMNS = {
        'id_origem',
        'data_limite_embargo',
        'autorizar_publicacao',
        'curso_nome',
        'dc.date.submitted',
    }

    # 7. Geração da Estrutura SAF (hierárquica por polo/coleção)
    print("Gerando estrutura SAF hierárquica (por polo/coleção)...")
    os.makedirs(saf_bundle_dir, exist_ok=True)
    write_access_policies(Path(saf_bundle_dir), access_policies)

    routing_report = []
    unmapped_count = 0

    for row_dict in df.to_dict(orient='records'):
        id_origem = row_dict['id_origem']
        curso_nome = row_dict.get('curso_nome')

        # Resolver roteamento: curso_nome → path da coleção
        target_path = resolve_collection_for_curso(curso_nome, curso_mapping)
        if target_path:
            subpath = get_saf_subpath(target_path)
            item_dir = os.path.join(saf_bundle_dir, str(subpath), f'item_{id_origem}')
            routing_status = 'OK'
        else:
            item_dir = os.path.join(saf_bundle_dir, '_unmapped', f'item_{id_origem}')
            routing_status = 'UNMAPPED'
            unmapped_count += 1

        routing_report.append({
            'id_origem': id_origem,
            'curso_nome': curso_nome or '',
            'target_path': target_path or '_unmapped',
            'status': routing_status,
        })

        os.makedirs(item_dir, exist_ok=True)
        root = ET.Element('dublin_core', schema='dc')

        invalid_xml_chars = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')

        def add_dcvalue(element, qualifier, language, value):
            if pd.notna(value) and str(value).strip() != "":
                for v in str(value).split('||'):
                    v = v.strip()
                    if v:
                        v_clean = invalid_xml_chars.sub('', v)
                        dcval = ET.SubElement(root, 'dcvalue', element=element, qualifier=qualifier)
                        if language:
                            dcval.set('language', language)
                        dcval.text = v_clean

        for col_name, val in row_dict.items():
            if pd.isna(val) or str(val).strip() == "":
                continue

            # Pular colunas de controle (não geram metadados DC)
            if col_name in EXCLUDED_COLUMNS:
                continue

            if col_name.startswith('dc.'):
                parts = col_name.split('.')
                schema = parts[0]
                element = parts[1]

                qualifier = 'none'
                language = None

                if len(parts) > 2:
                    qual_lang = parts[2]
                    if '[' in qual_lang and ']' in qual_lang:
                        qualifier = qual_lang.split('[')[0]
                        language = qual_lang.split('[')[1].replace(']', '')
                    else:
                        qualifier = qual_lang
                else:
                    if '[' in element and ']' in element:
                        element_part = element.split('[')[0]
                        language = element.split('[')[1].replace(']', '')
                        element = element_part

                add_dcvalue(element, qualifier, language, val)

        xml_str = ET.tostring(root, encoding='utf-8')
        parsed_xml = minidom.parseString(xml_str)
        pretty_xml = parsed_xml.toprettyxml(indent="  ", encoding="utf-8").decode('utf-8')

        with open(os.path.join(item_dir, 'dublin_core.xml'), 'w', encoding='utf-8') as f:
            f.write(pretty_xml)

    # Exportar relatório de roteamento
    routing_csv = Path('routing_report.csv')
    with open(routing_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['id_origem', 'curso_nome', 'target_path', 'status'])
        writer.writeheader()
        writer.writerows(routing_report)

    print(f"Relatório de roteamento exportado: {routing_csv}")
    if unmapped_count > 0:
        print(f"⚠️  ATENÇÃO: {unmapped_count} publicações sem mapeamento de curso → colocadas em '_unmapped/'")
    print("Geração do pacote SAF concluída com sucesso.")
