"""Regras de acesso compartilhadas pela geração e importação do SAF."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd


ACCESS_POLICIES_FILENAME = "access_policies.json"
SAF_RESTRICTED_GROUP = "Administrator"

_RESTRICTION_RE = re.compile(
    r"\b(restrito|restrição|embargo|liberação|sigilo|confidencial|"
    r"acesso\s+restrito|somente\s+admin|sem\s+autoriza[çc][aã]o|"
    r"n[aã]o\s+autoriza[a-zçãõ]*|autoriza[çc][aã]o\s+(pendente|negada))\b",
    flags=re.IGNORECASE,
)
_FALSE_VALUES = {"0", "false", "f", "n", "no", "não", "nao"}


@dataclass(frozen=True)
class AccessPolicy:
    """Política que deve ser aplicada aos bitstreams de uma publicação."""

    access_type: str
    start_date: date | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.access_type not in {"embargo", "restricted"}:
            raise ValueError(f"Tipo de acesso inválido: {self.access_type}")
        if self.access_type == "embargo" and self.start_date is None:
            raise ValueError("Um embargo precisa de uma data de liberação")

    def as_dict(self) -> dict[str, str | None]:
        return {
            "type": self.access_type,
            "startDate": self.start_date.isoformat() if self.start_date else None,
            "reason": self.reason,
        }


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    try:
        if bool(pd.isna(value)):
            return False
    except (TypeError, ValueError):
        pass
    return str(value).strip() != ""


def parse_embargo_date(value: Any) -> date | None:
    """Converte datas do PostgreSQL/Pandas para uma data ISO."""
    if not _has_value(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    parsed = pd.to_datetime(str(value).strip(), errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _is_explicit_false(value: Any) -> bool:
    if not _has_value(value):
        return False
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)):
        return value == 0
    return str(value).strip().casefold() in _FALSE_VALUES


def determine_access_policy(
    embargo_value: Any,
    authorize_value: Any = None,
    provenance: Any = None,
    note: Any = None,
    *,
    today: date | None = None,
) -> AccessPolicy | None:
    """Determina se os anexos devem ficar embargados ou restritos.

    Uma data válida é soberana: se ainda não chegou, o acesso anônimo começa
    nela; se já chegou, o embargo terminou. Valores de data inválidos são
    tratados de forma segura como restrição sem liberação automática.
    """
    today = today or date.today()

    if _has_value(embargo_value):
        embargo_date = parse_embargo_date(embargo_value)
        if embargo_date is None:
            return AccessPolicy(
                "restricted",
                reason=f"Data de embargo inválida na origem: {embargo_value}",
            )
        if embargo_date > today:
            return AccessPolicy(
                "embargo",
                start_date=embargo_date,
                reason=f"Embargo até {embargo_date.isoformat()}",
            )
        # A data é o primeiro dia em que Anonymous pode ler o bitstream.
        return None

    if _is_explicit_false(authorize_value):
        return AccessPolicy("restricted", reason="Publicação não autorizada")

    restriction_text = " ".join(
        str(value) for value in (provenance, note) if _has_value(value)
    )
    if restriction_text and _RESTRICTION_RE.search(restriction_text):
        return AccessPolicy("restricted", reason=restriction_text)

    return None


def write_access_policies(
    saf_bundle_dir: Path, policies: dict[int, AccessPolicy | None]
) -> None:
    """Grava o manifesto de acesso fora das pastas de itens do SAF."""
    policy_path = saf_bundle_dir / ACCESS_POLICIES_FILENAME
    serialized = {
        str(source_id): policy.as_dict()
        for source_id, policy in policies.items()
        if policy is not None
    }
    policy_path.write_text(
        json.dumps(serialized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_access_policies(saf_bundle_dir: Path) -> dict[int, AccessPolicy]:
    policy_path = saf_bundle_dir / ACCESS_POLICIES_FILENAME
    if not policy_path.is_file():
        return {}

    serialized = json.loads(policy_path.read_text(encoding="utf-8"))
    policies = {}
    for source_id, data in serialized.items():
        policies[int(source_id)] = AccessPolicy(
            access_type=data["type"],
            start_date=parse_embargo_date(data.get("startDate")),
            reason=data.get("reason"),
        )
    return policies


def build_contents_entry(filename: str, policy: AccessPolicy | None) -> str:
    """Monta uma linha SAF, restringindo o arquivo antes mesmo da importação."""
    if policy is None:
        return filename
    return f"{filename}\tpermissions:-r '{SAF_RESTRICTED_GROUP}'"


def contents_entry_filename(line: str) -> str:
    """Extrai o nome do arquivo de uma linha SAF que pode conter opções."""
    return line.split("\t", 1)[0].strip()
