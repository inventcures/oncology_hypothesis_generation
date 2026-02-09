import httpx
import logging
import os
import numpy as np
from typing import List, Dict, Optional, Tuple
from Bio.PDB import PDBParser, Selection, NeighborSearch, PDBIO
from Bio.PDB.Structure import Structure
from Bio.PDB.Residue import Residue
from io import StringIO
import tempfile
from scipy.spatial import ConvexHull, Delaunay
from scipy.cluster.hierarchy import fcluster, linkage
from collections import defaultdict
import re

logger = logging.getLogger(__name__)


class StructureAgent:
    """
    Virtual Structural Biologist (VSB) - Module A
    Fetches AlphaFold structures and performs druggability analysis.
    """

    def __init__(self):
        self.af_db_url = "https://alphafold.ebi.ac.uk/files"
        self.uniprot_url = "https://rest.uniprot.org/uniprotkb/search"
        # Hydrophobic residues important for binding pockets
        self.hydrophobic_residues = {
            "ALA",
            "VAL",
            "LEU",
            "ILE",
            "MET",
            "PHE",
            "TRP",
            "PRO",
        }
        self.polar_residues = {"SER", "THR", "ASN", "GLN", "TYR", "CYS"}
        self.charged_residues = {"ASP", "GLU", "LYS", "ARG", "HIS"}

    async def get_uniprot_id(self, gene_symbol: str) -> Optional[str]:
        """Maps Gene Symbol to Uniprot ID using Uniprot API."""
        params = {
            "query": f"gene:{gene_symbol} AND organism_id:9606 AND reviewed:true",
            "format": "json",
            "size": 1,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(self.uniprot_url, params=params)
                data = resp.json()
                if data.get("results"):
                    return data["results"][0]["primaryAccession"]
            except Exception as e:
                logger.error("Uniprot Search Error: %s", e)
        return None

    async def fetch_structure(
        self, gene_symbol: str, mutation: Optional[str] = None
    ) -> Dict:
        """
        Retrieves PDB, parses it, performs pocket detection, and analyzes druggability.

        Args:
            gene_symbol: Gene name (e.g., "KRAS")
            mutation: Optional mutation string (e.g., "G12C", "V600E")
        """
        uniprot_id = await self.get_uniprot_id(gene_symbol)
        if not uniprot_id:
            return {"error": f"Gene '{gene_symbol}' not found in Uniprot."}

        # Try v4, then v3
        versions = ["v4", "v3"]
        pdb_content = None
        pdb_url = ""

        async with httpx.AsyncClient(timeout=60.0) as client:
            for v in versions:
                url = f"{self.af_db_url}/AF-{uniprot_id}-F1-model_{v}.pdb"
                resp = await client.get(url)
                if resp.status_code == 200:
                    pdb_content = resp.text
                    pdb_url = url
                    break

        if not pdb_content:
            return {"error": f"AlphaFold structure not found for {uniprot_id}"}

        # Parse and analyze
        analysis = self._full_structure_analysis(pdb_content, uniprot_id, mutation)

        return {
            "gene": gene_symbol,
            "uniprot_id": uniprot_id,
            "pdb_url": pdb_url,
            "pdb_content": pdb_content,  # Return full PDB for Mol* rendering
            "analysis": analysis["metrics"],
            "druggability_score": analysis["druggability_score"],
            "pockets": analysis["pockets"],
            "mutation_analysis": analysis.get("mutation_analysis"),
            "binding_site_residues": analysis.get("binding_site_residues", []),
        }

    def _full_structure_analysis(
        self, pdb_text: str, struct_id: str, mutation: Optional[str] = None
    ) -> Dict:
        """
        Comprehensive structure analysis including:
        1. pLDDT confidence scoring
        2. Geometric pocket detection (Alpha-shape based)
        3. Druggability scoring per pocket
        4. Mutation position analysis
        """
        parser = PDBParser(QUIET=True)

        with tempfile.NamedTemporaryFile(mode="w+", suffix=".pdb", delete=False) as tmp:
            tmp.write(pdb_text)
            tmp_path = tmp.name

        try:
            structure = parser.get_structure(struct_id, tmp_path)
            model = structure[0]

            # Get all atoms and CA atoms
            all_atoms = list(structure.get_atoms())
            ca_atoms = [a for a in all_atoms if a.name == "CA"]

            if not ca_atoms:
                return {
                    "error": "No CA atoms found",
                    "pockets": [],
                    "druggability_score": 0,
                }

            # 1. Basic Metrics
            coords = np.array([a.get_coord() for a in all_atoms])
            ca_coords = np.array([a.get_coord() for a in ca_atoms])
            plddts = [a.get_bfactor() for a in ca_atoms]
            avg_plddt = np.mean(plddts)

            # 2. Pocket Detection using geometric analysis
            pockets = self._detect_pockets(model, ca_atoms, plddts)

            # 3. Calculate overall druggability
            if pockets:
                druggability_score = max(p["druggability_score"] for p in pockets)
            else:
                # Fallback: use pLDDT-based estimate
                druggability_score = min(avg_plddt / 100.0, 0.5)

            # 4. Mutation Analysis
            mutation_analysis = None
            if mutation:
                mutation_analysis = self._analyze_mutation(model, mutation, pockets)

            # 5. Collect binding site residues for visualization
            binding_residues = []
            for pocket in pockets[:3]:
                binding_residues.extend(pocket.get("residue_ids", []))

            return {
                "metrics": {
                    "center_of_mass": coords.mean(axis=0).tolist(),
                    "atom_count": len(all_atoms),
                    "residue_count": len(ca_atoms),
                    "avg_plddt": float(avg_plddt),
                    "high_confidence_pct": float(
                        np.mean([p > 70 for p in plddts]) * 100
                    ),
                    "disordered_regions": self._find_disordered_regions(
                        ca_atoms, plddts
                    ),
                },
                "pockets": pockets[:5],  # Top 5 pockets
                "druggability_score": float(druggability_score),
                "mutation_analysis": mutation_analysis,
                "binding_site_residues": list(set(binding_residues)),
            }

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _detect_pockets(self, model, ca_atoms: List, plddts: List[float]) -> List[Dict]:
        """
        Geometric pocket detection algorithm:
        1. Find surface residues using neighbor density
        2. Identify concave regions using local geometry
        3. Cluster into pockets
        4. Score druggability based on composition
        """
        pockets = []

        # Get all residues with their properties
        residues = []
        for chain in model:
            for residue in chain:
                if "CA" in residue:
                    ca = residue["CA"]
                    res_info = {
                        "residue": residue,
                        "id": residue.get_id()[1],
                        "resname": residue.get_resname(),
                        "coord": ca.get_coord(),
                        "plddt": ca.get_bfactor(),
                        "chain": chain.id,
                    }
                    residues.append(res_info)

        if len(residues) < 10:
            return []

        coords = np.array([r["coord"] for r in residues])

        # 1. Find surface residues (low neighbor density at 10Å)
        surface_residues = []
        for i, res in enumerate(residues):
            distances = np.linalg.norm(coords - res["coord"], axis=1)
            neighbors_10A = np.sum((distances > 0) & (distances < 10))
            neighbors_5A = np.sum((distances > 0) & (distances < 5))

            # Surface residues have fewer neighbors
            if neighbors_10A < 25 or neighbors_5A < 8:
                res["surface_score"] = 1.0 - (neighbors_10A / 40.0)
                res["local_density"] = neighbors_5A
                surface_residues.append(res)

        if len(surface_residues) < 5:
            return []

        # 2. Find concave regions (potential binding sites)
        # Use local curvature estimation
        surface_coords = np.array([r["coord"] for r in surface_residues])

        pocket_candidates = []
        for i, res in enumerate(surface_residues):
            # Get local neighborhood
            distances = np.linalg.norm(surface_coords - res["coord"], axis=1)
            local_mask = (distances > 0) & (distances < 12)
            local_neighbors = [surface_residues[j] for j in np.where(local_mask)[0]]

            if len(local_neighbors) >= 4:
                # Calculate local concavity
                local_coords = np.array([n["coord"] for n in local_neighbors])
                centroid = local_coords.mean(axis=0)

                # Vector from centroid to residue
                to_residue = res["coord"] - centroid

                # Estimate concavity: if residue is "inside" relative to neighbors, it's concave
                concavity = -np.dot(to_residue, to_residue) / (
                    np.linalg.norm(to_residue) + 1e-6
                )

                # Check for pocket-like environment (mix of residue types)
                local_resnames = [n["resname"] for n in local_neighbors]
                hydrophobic_count = sum(
                    1 for r in local_resnames if r in self.hydrophobic_residues
                )
                polar_count = sum(1 for r in local_resnames if r in self.polar_residues)

                if hydrophobic_count >= 2 and res["plddt"] > 60:
                    pocket_candidates.append(
                        {
                            "center_residue": res,
                            "neighbors": local_neighbors,
                            "concavity": concavity,
                            "hydrophobic_ratio": hydrophobic_count
                            / len(local_neighbors),
                            "polar_ratio": polar_count / len(local_neighbors),
                        }
                    )

        if not pocket_candidates:
            return []

        # 3. Cluster pocket candidates
        candidate_coords = np.array(
            [p["center_residue"]["coord"] for p in pocket_candidates]
        )

        if len(candidate_coords) >= 2:
            Z = linkage(candidate_coords, method="average")
            clusters = fcluster(Z, t=15, criterion="distance")  # 15Å clustering
        else:
            clusters = [1] * len(candidate_coords)

        # 4. Build pocket objects from clusters
        cluster_pockets = defaultdict(list)
        for i, cluster_id in enumerate(clusters):
            cluster_pockets[cluster_id].append(pocket_candidates[i])

        for cluster_id, members in cluster_pockets.items():
            if len(members) < 2:
                continue

            # Aggregate pocket properties
            all_residues = set()
            all_coords = []
            total_hydrophobic = 0
            total_polar = 0
            avg_plddt = 0

            for m in members:
                all_residues.add(m["center_residue"]["id"])
                all_coords.append(m["center_residue"]["coord"])
                avg_plddt += m["center_residue"]["plddt"]
                for n in m["neighbors"]:
                    all_residues.add(n["id"])
                total_hydrophobic += m["hydrophobic_ratio"]
                total_polar += m["polar_ratio"]

            center = np.mean(all_coords, axis=0)
            avg_plddt /= len(members)
            avg_hydrophobic = total_hydrophobic / len(members)
            avg_polar = total_polar / len(members)

            # Calculate pocket volume estimate (convex hull of residues)
            pocket_coords = np.array(all_coords)
            if len(pocket_coords) >= 4:
                try:
                    hull = ConvexHull(pocket_coords)
                    volume = hull.volume
                except Exception:
                    volume = len(all_residues) * 150  # Rough estimate
            else:
                volume = len(all_residues) * 150

            # 5. Druggability Scoring
            # Based on: size, hydrophobicity, confidence, enclosure
            size_score = min(volume / 500, 1.0)  # Ideal pocket ~500 Å³
            hydrophobic_score = avg_hydrophobic * 0.8 + avg_polar * 0.2
            confidence_score = avg_plddt / 100.0
            enclosure_score = min(len(all_residues) / 20, 1.0)

            druggability = (
                0.3 * size_score
                + 0.3 * hydrophobic_score
                + 0.2 * confidence_score
                + 0.2 * enclosure_score
            )

            # Color coding based on druggability
            if druggability > 0.7:
                color = "#22c55e"  # Green - High
                label = "High"
            elif druggability > 0.5:
                color = "#3b82f6"  # Blue - Medium
                label = "Medium"
            else:
                color = "#f59e0b"  # Amber - Low
                label = "Low"

            pockets.append(
                {
                    "id": f"pocket_{cluster_id}",
                    "name": f"Binding Pocket {cluster_id}",
                    "center": center.tolist(),
                    "volume_A3": float(volume),
                    "residue_count": len(all_residues),
                    "residue_ids": sorted(list(all_residues)),
                    "avg_plddt": float(avg_plddt),
                    "hydrophobic_ratio": float(avg_hydrophobic),
                    "polar_ratio": float(avg_polar),
                    "druggability_score": float(druggability),
                    "druggability_label": label,
                    "color": color,
                }
            )

        # Sort by druggability
        pockets.sort(key=lambda x: x["druggability_score"], reverse=True)

        return pockets

    def _analyze_mutation(self, model, mutation_str: str, pockets: List[Dict]) -> Dict:
        """
        Analyze mutation position relative to binding pockets.

        Args:
            mutation_str: e.g., "G12C", "V600E"
        """
        # Parse mutation string
        match = re.match(r"([A-Z])(\d+)([A-Z])", mutation_str.upper())
        if not match:
            return {"error": f"Could not parse mutation: {mutation_str}"}

        wt_aa = match.group(1)
        position = int(match.group(2))
        mut_aa = match.group(3)

        # Find the residue
        mutation_residue = None
        mutation_coord = None

        for chain in model:
            for residue in chain:
                if residue.get_id()[1] == position and "CA" in residue:
                    mutation_residue = residue
                    mutation_coord = residue["CA"].get_coord()
                    break

        if mutation_residue is None:
            return {
                "position": position,
                "wt_aa": wt_aa,
                "mut_aa": mut_aa,
                "found": False,
                "message": f"Residue {position} not found in structure",
            }

        actual_resname = mutation_residue.get_resname()
        plddt = mutation_residue["CA"].get_bfactor()

        # Check proximity to pockets
        pocket_proximity = []
        in_pocket = False
        closest_pocket = None
        min_distance = float("inf")

        for pocket in pockets:
            pocket_center = np.array(pocket["center"])
            distance = np.linalg.norm(mutation_coord - pocket_center)

            if position in pocket.get("residue_ids", []):
                in_pocket = True
                pocket_proximity.append(
                    {
                        "pocket_id": pocket["id"],
                        "pocket_name": pocket["name"],
                        "relationship": "INSIDE",
                        "distance_to_center": float(distance),
                    }
                )
            elif distance < 15:
                pocket_proximity.append(
                    {
                        "pocket_id": pocket["id"],
                        "pocket_name": pocket["name"],
                        "relationship": "ADJACENT" if distance < 8 else "NEARBY",
                        "distance_to_center": float(distance),
                    }
                )

            if distance < min_distance:
                min_distance = distance
                closest_pocket = pocket["id"]

        # Assess mutation impact
        if in_pocket:
            impact = "HIGH - Mutation is inside a predicted binding pocket"
            impact_score = 0.9
        elif min_distance < 8:
            impact = "MEDIUM - Mutation is adjacent to a binding pocket"
            impact_score = 0.6
        elif min_distance < 15:
            impact = "LOW - Mutation is near but not in a binding pocket"
            impact_score = 0.3
        else:
            impact = "MINIMAL - Mutation is distant from predicted binding sites"
            impact_score = 0.1

        return {
            "position": position,
            "wt_aa": wt_aa,
            "mut_aa": mut_aa,
            "found": True,
            "actual_residue": actual_resname,
            "coordinate": mutation_coord.tolist() if mutation_coord is not None else [],
            "plddt": float(plddt),
            "in_binding_pocket": in_pocket,
            "closest_pocket": closest_pocket,
            "distance_to_closest_pocket": float(min_distance),
            "pocket_proximity": pocket_proximity,
            "impact_assessment": impact,
            "impact_score": float(impact_score),
        }

    def _find_disordered_regions(
        self, ca_atoms: List, plddts: List[float]
    ) -> List[Dict]:
        """Find regions with low pLDDT (< 50) indicating disorder."""
        disordered = []
        current_region = []

        for i, (atom, plddt) in enumerate(zip(ca_atoms, plddts)):
            res_id = atom.get_parent().get_id()[1]
            if plddt < 50:
                current_region.append(res_id)
            else:
                if len(current_region) >= 5:
                    disordered.append(
                        {
                            "start": current_region[0],
                            "end": current_region[-1],
                            "length": len(current_region),
                        }
                    )
                current_region = []

        if len(current_region) >= 5:
            disordered.append(
                {
                    "start": current_region[0],
                    "end": current_region[-1],
                    "length": len(current_region),
                }
            )

        return disordered
