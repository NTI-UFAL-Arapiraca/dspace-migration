import os
import re
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom
import pandas as pd
import psycopg2
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configurações de Conexão com o Banco de Dados (variáveis em .env)
# ---------------------------------------------------------------------------
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5440")
DB_NAME = os.getenv("DB_NAME", "biblioteca")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")


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
    print(f"Lendo consulta SQL de: {sql_file}")
    with open(sql_file, "r", encoding="utf-8") as f:
        sql_query = f.read()

    print(f"Conectando ao banco de dados {DB_NAME} em {DB_HOST}:{DB_PORT}...")
    conn = connect_db()
    try:
        df = pd.read_sql_query(sql_query, conn)
        return df
    finally:
        conn.close()


def process_data(
    input_csv=None,
    sql_file="sql/extract_csv.sql",
    output_csv="processed_data.csv",
    embargo_csv="embargoed_items.csv",
    saf_bundle_dir="saf_bundle",
):
    print("Iniciando o processamento dos dados...")

    if input_csv and os.path.exists(input_csv):
        print(f"Carregando dados a partir do arquivo CSV de entrada: {input_csv}")
        df = pd.read_csv(input_csv)
    else:
        actual_sql_file = sql_file
        if not os.path.exists(actual_sql_file) and os.path.exists("docs/extract_csv.sql"):
            actual_sql_file = "docs/extract_csv.sql"

        if not os.path.exists(actual_sql_file):
            raise FileNotFoundError(
                f"Arquivo SQL não encontrado em '{sql_file}' nem em 'docs/extract_csv.sql'."
            )

        df = fetch_data_from_db(actual_sql_file)

    print(f"Total de registros carregados: {df.shape[0]}")

    # 1. Limpeza de HTML
    print("Limpando tags HTML...")
    html_pattern = re.compile(r'<(?!\/?i\b)[^>]+>|&nbsp;', flags=re.IGNORECASE)

    html_cols = [
        'dc.title',
        'dc.description.abstract[pt_BR]',
        'dc.description.abstract[en]',
        'dc.description.note',
        'dc.identifier.citation',
    ]

    def clean_html(val):
        if pd.isna(val):
            return val
        return html_pattern.sub('', str(val)).strip()

    for col in html_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_html)

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

    # 4. Triagem de Observações vs Citações
    print("Realizando triagem de Observações vs Citações...")
    note_keywords = re.compile(r'\b(acervo|impress[a-z]*|bca|biblioteca)\b', flags=re.IGNORECASE)
    citation_keywords = re.compile(
        r'\b(v\.|n\.|p\.|vol\.|issn|doi|http|https|editora|revista|anais|scielo)\b',
        flags=re.IGNORECASE,
    )

    if 'dc.description.note' in df.columns and 'dc.identifier.citation' in df.columns:
        for idx, row in df.iterrows():
            note_val = row['dc.description.note']
            cit_val = row['dc.identifier.citation']

            if pd.notna(note_val) and str(note_val).strip() != "":
                text = str(note_val)
                if note_keywords.search(text):
                    df.at[idx, 'dc.description.note'] = text
                    df.at[idx, 'dc.identifier.citation'] = None
                elif citation_keywords.search(text):
                    df.at[idx, 'dc.identifier.citation'] = text
                    df.at[idx, 'dc.description.note'] = None
            elif pd.notna(cit_val) and str(cit_val).strip() != "":
                text = str(cit_val)
                if note_keywords.search(text):
                    df.at[idx, 'dc.description.note'] = text
                    df.at[idx, 'dc.identifier.citation'] = None

    # 5. Extração de Itens Embargados
    print("Extraindo itens embargados...")
    embargo_mask = pd.notna(df['data_limite_embargo']) | (
        df['dc.description.note'].str.contains(r'restrito|embargo|liberação', case=False, na=False)
    )

    embargo_df = df[embargo_mask].copy()
    embargo_output = embargo_df[['id_origem', 'data_limite_embargo', 'dc.description.note']].copy()
    embargo_output.rename(columns={'dc.description.note': 'motivo'}, inplace=True)
    embargo_output.to_csv(embargo_csv, index=False)
    print(f"Exportados {len(embargo_output)} itens embargados para {embargo_csv}")

    # 6. Exportação do processed_data.csv
    print(f"Exportando dados processados para {output_csv}...")
    df.to_csv(output_csv, index=False)

    # 7. Geração da Estrutura SAF
    print("Gerando estrutura SAF (Simple Archive Format)...")
    os.makedirs(saf_bundle_dir, exist_ok=True)

    for row_dict in df.to_dict(orient='records'):
        id_origem = row_dict['id_origem']
        item_dir = os.path.join(saf_bundle_dir, f'item_{id_origem}')
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

    print("Geração do pacote SAF concluída com sucesso.")


if __name__ == '__main__':
    process_data(
        sql_file='sql/extract_csv.sql',
        output_csv='processed_data.csv',
        embargo_csv='embargoed_items.csv',
        saf_bundle_dir='saf_bundle',
    )
