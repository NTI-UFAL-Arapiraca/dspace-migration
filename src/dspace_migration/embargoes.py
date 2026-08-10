"""Aplica no DSpace as datas de liberação dos embargos importados via SAF."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from dspace_rest_client.client import DSpaceClient
from dspace_rest_client.models import Item, ResourcePolicy

from dspace_migration.access import AccessPolicy, read_access_policies
from dspace_migration.statistics import read_mapfiles


logger = logging.getLogger(__name__)
MIGRATION_POLICY_NAME = "Embargo da migração Odoo"


@dataclass
class EmbargoApplicationResult:
    items: int = 0
    bitstreams: int = 0
    without_bitstreams: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0


def find_embargo_policies(saf_bundle_dir: str | Path) -> dict[int, AccessPolicy]:
    """Lê os manifestos locais e retorna apenas embargos com data de liberação."""
    try:
        policies = read_access_policies(Path(saf_bundle_dir))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Manifesto de acesso inválido: {exc}") from exc
    return {
        source_id: policy
        for source_id, policy in policies.items()
        if policy.access_type == "embargo"
    }


def _find_anonymous_group(client: DSpaceClient):
    groups = client.search_groups_by_metadata_iter("Anonymous")
    anonymous = next((group for group in groups if group.name == "Anonymous"), None)
    if anonymous is None:
        raise RuntimeError("Grupo padrão 'Anonymous' não encontrado no DSpace")
    return anonymous


def _original_bitstreams(client: DSpaceClient, item_dso) -> list:
    item = Item.from_dso(item_dso)
    bundles = client.get_bundles_iter(parent=item)
    originals = [bundle for bundle in bundles if bundle.name == "ORIGINAL"]
    bitstreams = []
    for bundle in originals:
        bitstreams.extend(client.get_bitstreams_iter(bundle=bundle))
    return bitstreams


def _ensure_embargo_policy(
    client: DSpaceClient,
    bitstream_uuid: str,
    anonymous_uuid: str,
    policy: AccessPolicy,
) -> str:
    start_date = policy.start_date.isoformat()
    existing = list(
        client.get_resource_policies_iter(parent=bitstream_uuid, action="READ")
    )
    migration_policy = next(
        (candidate for candidate in existing if candidate.name == MIGRATION_POLICY_NAME),
        None,
    )

    if migration_policy is not None:
        if migration_policy.startDate == start_date:
            return "unchanged"
        response = client.api_patch(
            url=migration_policy.links["self"]["href"],
            operation=client.PatchOperation.REPLACE,
            path="/startDate",
            value=start_date,
        )
        if response is None or response.status_code != 200:
            status = getattr(response, "status_code", "sem resposta")
            detail = getattr(response, "text", "")
            raise RuntimeError(
                f"Falha ao atualizar embargo do bitstream {bitstream_uuid} "
                f"[{status}]: {detail[:300]}"
            )
        return "updated"

    resource_policy = ResourcePolicy({
        "name": MIGRATION_POLICY_NAME,
        "description": policy.reason,
        "policyType": "TYPE_CUSTOM",
        "action": "READ",
        "startDate": start_date,
        "endDate": None,
        "type": "resourcepolicy",
    })
    created = client.create_resource_policy(
        resource_policy,
        parent=bitstream_uuid,
        group=anonymous_uuid,
    )
    if created is None:
        raise RuntimeError(f"Falha ao criar embargo para o bitstream {bitstream_uuid}")
    return "created"


def apply_embargoes(
    saf_bundle_dir: str | Path | None = None,
    api_url: str | None = None,
    user: str | None = None,
    password: str | None = None,
    *,
    dry_run: bool = False,
) -> EmbargoApplicationResult:
    """Cria políticas READ para Anonymous, válidas a partir do fim do embargo.

    Os bitstreams chegam ao DSpace restritos ao grupo Administrator pelo arquivo
    ``contents``. Esta etapa acrescenta o acesso anônimo futuro; se falhar, o
    comportamento seguro é mantido e o PDF continua privado.
    """
    load_dotenv()
    saf_dir = Path(saf_bundle_dir or os.getenv("SAF_BUNDLE_DIR", "saf_bundle"))
    embargo_policies = find_embargo_policies(saf_dir)
    result = EmbargoApplicationResult(items=len(embargo_policies))

    if not embargo_policies:
        logger.info("Nenhum embargo ativo com data de liberação encontrado.")
        return result

    id_to_handle = read_mapfiles(str(saf_dir))
    missing_handles = sorted(set(embargo_policies) - set(id_to_handle))
    if missing_handles:
        logger.warning(
            "%d item(ns) embargado(s) ainda não possuem handle e serão ignorados: %s",
            len(missing_handles),
            missing_handles[:10],
        )

    api_endpoint = api_url or os.getenv(
        "DSPACE_API_URL", "http://localhost:8080/server/api"
    )
    client = DSpaceClient(
        api_endpoint=api_endpoint,
        username=user or os.getenv("DSPACE_API_USER", "test@test.edu"),
        password=password or os.getenv("DSPACE_API_PASSWORD", "admin"),
    )
    if not client.authenticate():
        raise RuntimeError("Falha na autenticação com a API REST do DSpace")
    anonymous = _find_anonymous_group(client)

    errors = []
    for source_id, policy in embargo_policies.items():
        handle = id_to_handle.get(source_id)
        if handle is None:
            continue
        item_dso = client.resolve_identifier_to_dso(handle)
        if item_dso is None:
            errors.append(f"item_{source_id}: handle {handle} não resolvido")
            continue

        bitstreams = _original_bitstreams(client, item_dso)
        if not bitstreams:
            result.without_bitstreams += 1
            logger.warning(
                "item_%s não possui bitstreams no bundle ORIGINAL; "
                "nenhuma política de arquivo é necessária.",
                source_id,
            )
            continue

        result.bitstreams += len(bitstreams)
        for bitstream in bitstreams:
            if dry_run:
                logger.info(
                    "[DRY-RUN] %s: liberar %s em %s",
                    source_id,
                    bitstream.uuid,
                    policy.start_date,
                )
                continue
            try:
                outcome = _ensure_embargo_policy(
                    client, bitstream.uuid, anonymous.uuid, policy
                )
                setattr(result, outcome, getattr(result, outcome) + 1)
            except RuntimeError as exc:
                errors.append(f"item_{source_id}: {exc}")

    if errors:
        sample = "\n  - ".join(errors[:10])
        raise RuntimeError(
            f"Não foi possível configurar {len(errors)} embargo(s). "
            f"Os PDFs permanecem restritos por segurança:\n  - {sample}"
        )

    logger.info(
        "Embargos aplicados: %d bitstreams (%d criados, %d atualizados, %d inalterados).",
        result.bitstreams,
        result.created,
        result.updated,
        result.unchanged,
    )
    return result
