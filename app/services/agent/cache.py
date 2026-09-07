import json
from collections import OrderedDict
from hashlib import sha256

from app.schemas.uploads import CalculationPlan, DataCatalog

_MAPPING_CACHE_MAX_SIZE = 64
_mapping_cache: OrderedDict[str, CalculationPlan] = OrderedDict()

def catalog_schema_fingerprint(
    upload_catalog: DataCatalog,
) -> str:
    schema_only = {
        "tables": [
            {
                "source_name": table.source_name,
                "columns": table.columns,
                "column_types": {
                    column: sorted(
                        {
                            type(row.get(column)).__name__
                            for row in table.rows
                            if row.get(column) is not None
                        }
                    )
                    for column in table.columns
                },
            }
            for table in upload_catalog.tables
        ],
    }
    encoded = json.dumps(schema_only, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def get_cached_analysis(schema_fingerprint: str) -> CalculationPlan | None:
    analysis = _mapping_cache.get(schema_fingerprint)
    if analysis is None:
        return None
    _mapping_cache.move_to_end(schema_fingerprint)
    return analysis.model_copy(deep=True)


def cache_analysis(
    schema_fingerprint: str,
    analysis: CalculationPlan,
) -> None:
    _mapping_cache[schema_fingerprint] = analysis.model_copy(deep=True)
    _mapping_cache.move_to_end(schema_fingerprint)
    while len(_mapping_cache) > _MAPPING_CACHE_MAX_SIZE:
        _mapping_cache.popitem(last=False)

