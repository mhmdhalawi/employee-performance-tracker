from unittest import TestCase

from app.schemas.tables import AnalyzeTablesRequest
from app.services.tables import catalog_from_tables


class ReceivedTableCatalogTests(TestCase):
    def test_catalog_derives_stable_columns_and_source_rows(self) -> None:
        request = AnalyzeTablesRequest.model_validate(
            {
                "tables": [
                    {
                        "source_name": "Projects",
                        "rows": [
                            {"record_id": "PRJ-1", "employee_id": "EMP-1"},
                            {"employee_id": "EMP-2", "status": "complete"},
                        ],
                    }
                ]
            }
        )

        catalog = catalog_from_tables(request)
        table = catalog.tables[0]

        self.assertEqual(table.columns, ["record_id", "employee_id", "status"])
        self.assertEqual(table.row_count, 2)
        self.assertEqual(table.rows[0]["_source_row"], 1)
        self.assertEqual(table.rows[1]["_source_row"], 2)
        self.assertNotIn("status", table.rows[0])
