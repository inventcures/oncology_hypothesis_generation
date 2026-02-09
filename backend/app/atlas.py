import cellxgene_census
import logging
import tiledbsoma as soma
import numpy as np
import pandas as pd
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class AtlasAgent:
    def __init__(self):
        self.census_version = "latest"

    def fetch_tumor_atlas(self, tissue: str, limit: int = 500) -> Dict[str, Any]:
        """
        Fetches single-cell embeddings and metadata for a specific tissue.
        Returns a simplified dictionary for frontend visualization.
        """
        logger.info("Connecting to CELLxGENE Census (%s)...", self.census_version)

        try:
            with cellxgene_census.open_soma(
                census_version=self.census_version
            ) as census:
                # 1. Query for human data in the specified tissue
                # Filter for primary tumor if possible, otherwise just the tissue
                obs_value_filter = f"tissue_general == '{tissue}'"

                logger.info("Querying for %s...", tissue)

                # Fetch obs (metadata) and embeddings (obsm)
                # Note: This is a heavy operation, so we limit significantly for the prototype
                experiment = census["census_data"]["homo_sapiens"]

                # Using read() with limits is complex in SOMA, so we fetch identifiers first
                # For this prototype, we'll iterate and break early

                query = experiment.axis_query(
                    measurement_name="RNA",
                    obs_query=soma.AxisQuery(value_filter=obs_value_filter),
                )

                # Fetch metadata (obs)
                obs_df = (
                    query.obs(column_names=["soma_joinid", "cell_type", "disease"])
                    .concat()
                    .to_pandas()
                )

                if obs_df.empty:
                    logger.info("No cells found for tissue: %s", tissue)
                    return {"cells": []}

                # Subsample for the frontend
                if len(obs_df) > limit:
                    obs_df = obs_df.sample(limit)

                # We need coordinates. Census often stores embeddings in 'obsm'.
                # However, pre-calculated UMAPs aren't always standard across all datasets in Census.
                # FALLBACK: We will generate synthetic UMAP coords for the prototype
                # because running UMAP on the fly on a standard server is too slow/heavy.
                # In a real production app, we would pre-compute these or fetch from a specific dataset.

                logger.info("Fetched %d cells. Generating projection...", len(obs_df))

                cells = []
                # Mocking UMAP generation based on cell types to create clusters
                # (Real implementation would fetch 'X_umap' from specific datasets if available)

                unique_types = obs_df["cell_type"].unique()
                type_centers = {
                    t: (np.random.uniform(-10, 10), np.random.uniform(-10, 10))
                    for t in unique_types
                }

                for _, row in obs_df.iterrows():
                    center = type_centers[row["cell_type"]]
                    # Add noise
                    x = center[0] + np.random.normal(0, 1)
                    y = center[1] + np.random.normal(0, 1)

                    cells.append(
                        {
                            "id": str(row["soma_joinid"]),
                            "x": x,
                            "y": y,
                            "cell_type": row["cell_type"],
                            "disease": row["disease"],
                            "expression": np.random.uniform(
                                0, 5
                            ),  # Placeholder for gene expression
                        }
                    )

                return {"cells": cells}

        except Exception as e:
            logger.error("Atlas Error: %s", e)
            return {"cells": [], "error": str(e)}


# Test
if __name__ == "__main__":
    agent = AtlasAgent()
    # Test with "lung"
    data = agent.fetch_tumor_atlas("lung")
    print(f"Returned {len(data['cells'])} cells.")
    if data["cells"]:
        print(data["cells"][0])
