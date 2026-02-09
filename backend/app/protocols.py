import httpx
import logging
import os
import re
import hashlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class gRNACandidate:
    """Represents a CRISPR guide RNA candidate."""

    sequence: str
    pam: str
    position: int
    strand: str
    gc_content: float
    score: float
    off_target_risk: str


class ProtocolAgent:
    """
    Protocol Droid - Module D
    Generates experimental protocols with:
    1. LLM-powered contextual protocol generation
    2. Computational gRNA design for CRISPR experiments
    3. Cell line-specific optimization
    """

    def __init__(self):
        # Check for LLM API keys
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")

        # gRNA scoring parameters (based on Doench et al. 2016 - Rule Set 2)
        self.position_weights = {
            # Position-specific nucleotide preferences (simplified)
            # Positions 1-20 of the 20bp guide
            "G": [
                0.1,
                0.1,
                0.1,
                0.1,
                0.2,
                0.3,
                0.2,
                0.1,
                0.1,
                0.1,
                0.1,
                0.1,
                0.1,
                0.1,
                0.1,
                0.2,
                0.3,
                0.2,
                0.1,
                0.1,
            ],
            "C": [
                0.1,
                0.2,
                0.1,
                0.1,
                0.1,
                0.1,
                0.1,
                0.2,
                0.1,
                0.1,
                0.1,
                0.1,
                0.2,
                0.1,
                0.1,
                0.1,
                0.1,
                0.1,
                0.2,
                0.1,
            ],
        }

        # Common restriction sites to avoid
        self.restriction_sites = ["GAATTC", "GGATCC", "AAGCTT", "CTCGAG", "GCGGCCGC"]

        # Problematic sequences
        self.poly_t = "TTTT"  # Can cause premature termination

    async def generate_protocol(
        self,
        method: str,
        gene: str,
        cell_line: str,
        target_sequence: Optional[str] = None,
        use_llm: bool = True,
    ) -> Dict:
        """
        Generate a customized experimental protocol.

        Args:
            method: Experiment type (crispr, western, drug_assay, rnai, etc.)
            gene: Target gene symbol
            cell_line: Cell line to use
            target_sequence: Optional gene sequence for gRNA design
            use_llm: Whether to attempt LLM generation
        """

        method_key = method.lower()

        # Determine protocol type and generate
        if "crispr" in method_key or "knockout" in method_key or "ko" in method_key:
            protocol = await self._generate_crispr_protocol(
                gene, cell_line, target_sequence, use_llm
            )
        elif "western" in method_key or "blot" in method_key:
            protocol = await self._generate_western_protocol(gene, cell_line, use_llm)
        elif "drug" in method_key or "viability" in method_key or "ic50" in method_key:
            protocol = await self._generate_drug_assay_protocol(
                gene, cell_line, use_llm
            )
        elif "rnai" in method_key or "sirna" in method_key or "shrna" in method_key:
            protocol = await self._generate_rnai_protocol(gene, cell_line, use_llm)
        elif "immunofluorescence" in method_key or "if" in method_key:
            protocol = await self._generate_if_protocol(gene, cell_line, use_llm)
        elif "qpcr" in method_key or "rt-pcr" in method_key:
            protocol = await self._generate_qpcr_protocol(gene, cell_line, use_llm)
        else:
            protocol = await self._generate_general_protocol(
                method, gene, cell_line, use_llm
            )

        return protocol

    async def _generate_crispr_protocol(
        self, gene: str, cell_line: str, sequence: Optional[str], use_llm: bool
    ) -> Dict:
        """Generate CRISPR knockout protocol with gRNA design."""

        # 1. Design gRNAs
        grnas = []
        if sequence:
            grnas = self._design_grnas(sequence, gene)
        else:
            # Fetch sequence from Ensembl if not provided
            sequence = await self._fetch_gene_sequence(gene)
            if sequence:
                grnas = self._design_grnas(sequence, gene)

        # 2. Generate protocol content
        if use_llm and (self.openai_key or self.anthropic_key):
            content = await self._llm_generate_protocol(
                "CRISPR-Cas9 knockout",
                gene,
                cell_line,
                additional_context=f"gRNAs designed: {len(grnas)}",
            )
        else:
            content = self._crispr_template(gene, cell_line, grnas)

        # 3. Format gRNA table
        grna_table = self._format_grna_table(grnas) if grnas else None

        return {
            "title": f"CRISPR-Cas9 Knockout of {gene} in {cell_line} Cells",
            "type": "crispr",
            "content": content,
            "grnas": [
                {
                    "sequence": g.sequence,
                    "pam": g.pam,
                    "position": g.position,
                    "strand": g.strand,
                    "gc_content": round(g.gc_content, 1),
                    "score": round(g.score, 2),
                    "off_target_risk": g.off_target_risk,
                }
                for g in grnas[:5]
            ]
            if grnas
            else [],
            "grna_table": grna_table,
            "reagents": self._get_crispr_reagents(cell_line),
            "timeline": self._get_crispr_timeline(),
            "generated_by": "LLM"
            if (use_llm and (self.openai_key or self.anthropic_key))
            else "Template",
        }

    def _design_grnas(self, sequence: str, gene: str) -> List[gRNACandidate]:
        """
        Design gRNAs using computational scoring.

        Uses simplified Rule Set 2 (Doench et al. 2016) scoring:
        - GC content (40-70% optimal)
        - Position-specific nucleotide preferences
        - Avoid poly-T stretches
        - Avoid restriction sites
        """

        sequence = sequence.upper().replace("\n", "").replace(" ", "")
        candidates = []

        # Find all PAM sites (NGG for SpCas9)
        pam_pattern = r"(?=(.{20})(.GG))"

        for match in re.finditer(pam_pattern, sequence):
            guide = match.group(1)
            pam = match.group(2)
            position = match.start()

            # Calculate GC content
            gc_count = guide.count("G") + guide.count("C")
            gc_content = (gc_count / 20) * 100

            # Score the guide
            score = self._score_grna(guide, gc_content)

            # Determine off-target risk (simplified)
            off_target = self._estimate_off_target_risk(guide)

            if score > 0.3:  # Minimum threshold
                candidates.append(
                    gRNACandidate(
                        sequence=guide,
                        pam=pam,
                        position=position,
                        strand="+",
                        gc_content=gc_content,
                        score=score,
                        off_target_risk=off_target,
                    )
                )

        # Also search reverse complement
        rev_comp = self._reverse_complement(sequence)
        for match in re.finditer(pam_pattern, rev_comp):
            guide = match.group(1)
            pam = match.group(2)
            position = len(sequence) - match.start() - 23

            gc_count = guide.count("G") + guide.count("C")
            gc_content = (gc_count / 20) * 100
            score = self._score_grna(guide, gc_content)
            off_target = self._estimate_off_target_risk(guide)

            if score > 0.3:
                candidates.append(
                    gRNACandidate(
                        sequence=guide,
                        pam=pam,
                        position=position,
                        strand="-",
                        gc_content=gc_content,
                        score=score,
                        off_target_risk=off_target,
                    )
                )

        # Sort by score (descending)
        candidates.sort(key=lambda x: x.score, reverse=True)

        return candidates[:10]  # Return top 10

    def _score_grna(self, guide: str, gc_content: float) -> float:
        """
        Score a gRNA sequence (0-1 scale).

        Based on:
        - GC content (40-70% optimal)
        - Position-specific nucleotide preferences
        - Avoiding problematic sequences
        """

        score = 0.5  # Base score

        # GC content scoring (optimal: 40-70%)
        if 40 <= gc_content <= 70:
            score += 0.2
        elif 35 <= gc_content <= 75:
            score += 0.1
        elif gc_content < 30 or gc_content > 80:
            score -= 0.2

        # Position-specific scoring
        for i, nt in enumerate(guide):
            if nt in self.position_weights:
                score += self.position_weights[nt][i] * 0.02

        # Penalize poly-T (causes Pol III termination)
        if self.poly_t in guide:
            score -= 0.3

        # Penalize restriction sites
        for site in self.restriction_sites:
            if site in guide:
                score -= 0.1

        # Prefer G at position 20 (adjacent to PAM)
        if guide[-1] == "G":
            score += 0.1

        # Penalize G at position 1
        if guide[0] == "G":
            score -= 0.05

        return max(0, min(1, score))

    def _estimate_off_target_risk(self, guide: str) -> str:
        """Estimate off-target risk based on sequence complexity."""

        # Simple heuristic based on sequence uniqueness
        # In production, would use actual genome alignment

        # Count unique 10-mers
        kmers = set()
        for i in range(len(guide) - 9):
            kmers.add(guide[i : i + 10])

        uniqueness = len(kmers) / 11  # Max possible is 11

        # Check for common repeat patterns
        has_repeat = any(
            guide.count(guide[i : i + 4]) > 1 for i in range(len(guide) - 3)
        )

        if uniqueness > 0.9 and not has_repeat:
            return "Low"
        elif uniqueness > 0.7:
            return "Medium"
        else:
            return "High"

    def _reverse_complement(self, seq: str) -> str:
        """Get reverse complement of DNA sequence."""
        complement = {"A": "T", "T": "A", "G": "C", "C": "G", "N": "N"}
        return "".join(complement.get(nt, "N") for nt in reversed(seq))

    def _format_grna_table(self, grnas: List[gRNACandidate]) -> str:
        """Format gRNAs as markdown table."""

        if not grnas:
            return ""

        table = "| Rank | Sequence (5'→3') | PAM | Position | Strand | GC% | Score | Off-Target |\n"
        table += "|------|------------------|-----|----------|--------|-----|-------|------------|\n"

        for i, g in enumerate(grnas[:5], 1):
            table += f"| {i} | `{g.sequence}` | {g.pam} | {g.position} | {g.strand} | {g.gc_content:.0f}% | {g.score:.2f} | {g.off_target_risk} |\n"

        return table

    async def _fetch_gene_sequence(self, gene: str) -> Optional[str]:
        """Fetch gene coding sequence from Ensembl."""

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # First, get gene ID
                url = f"https://rest.ensembl.org/lookup/symbol/homo_sapiens/{gene}"
                resp = await client.get(
                    url, headers={"Content-Type": "application/json"}
                )

                if resp.status_code == 200:
                    data = resp.json()
                    gene_id = data.get("id")

                    if gene_id:
                        # Get sequence
                        seq_url = (
                            f"https://rest.ensembl.org/sequence/id/{gene_id}?type=cds"
                        )
                        seq_resp = await client.get(
                            seq_url, headers={"Content-Type": "text/plain"}
                        )

                        if seq_resp.status_code == 200:
                            return seq_resp.text[:3000]  # First 3kb

            except Exception as e:
                logger.error("Ensembl API error: %s", e)

        return None

    async def _llm_generate_protocol(
        self, method: str, gene: str, cell_line: str, additional_context: str = ""
    ) -> str:
        """Generate protocol using LLM API."""

        prompt = f"""Generate a detailed experimental protocol for:
- Method: {method}
- Target Gene: {gene}
- Cell Line: {cell_line}
{f"- Additional Context: {additional_context}" if additional_context else ""}

Include:
1. Objective
2. Materials and reagents with catalog numbers where possible
3. Step-by-step procedure with timing
4. Critical steps and tips
5. Expected results
6. Troubleshooting guide

Format as clean markdown suitable for a lab notebook."""

        if self.openai_key:
            return await self._call_openai(prompt)
        elif self.anthropic_key:
            return await self._call_anthropic(prompt)

        return None

    async def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API."""

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.openai_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are an expert molecular biologist writing detailed lab protocols.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 2000,
                    },
                )

                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]

            except Exception as e:
                logger.error("OpenAI API error: %s", e)

        return None

    async def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic API."""

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.anthropic_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 2000,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )

                if resp.status_code == 200:
                    return resp.json()["content"][0]["text"]

            except Exception as e:
                logger.error("Anthropic API error: %s", e)

        return None

    def _crispr_template(
        self, gene: str, cell_line: str, grnas: List[gRNACandidate]
    ) -> str:
        """Enhanced CRISPR template with gRNA information."""

        grna_section = ""
        if grnas:
            top_grna = grnas[0]
            grna_section = f"""
## Recommended gRNA Sequences

**Primary gRNA (Highest Score: {top_grna.score:.2f})**
- Sequence: `{top_grna.sequence}`
- PAM: {top_grna.pam}
- GC Content: {top_grna.gc_content:.0f}%
- Off-Target Risk: {top_grna.off_target_risk}
- Position: {top_grna.position} ({top_grna.strand} strand)

**Ordering Information:**
- For cloning into lentiCRISPRv2, order as:
  - Forward: `CACCG{top_grna.sequence}`
  - Reverse: `AAAC{self._reverse_complement(top_grna.sequence)}C`

{self._format_grna_table(grnas)}

*gRNAs scored using position-specific nucleotide preferences and GC content optimization.*
"""

        return f"""# CRISPR-Cas9 Knockout of {gene} in {cell_line} Cells

**Objective:** To validate the functional role of {gene} via CRISPR-Cas9 mediated knockout.

{grna_section}

## Materials

### Plasmids & Cloning
- **Vector:** lentiCRISPRv2 (Addgene #52961) or pSpCas9(BB)-2A-Puro (Addgene #62988)
- **Packaging plasmids:** psPAX2 (Addgene #12260) + pMD2.G (Addgene #12259)
- **Restriction enzymes:** BsmBI (for lentiCRISPRv2) or BbsI (for pX459)

### Cell Culture
- **Target cells:** {cell_line}
- **Media:** DMEM/RPMI + 10% FBS + 1% Pen/Strep (verify for {cell_line})
- **Selection:** Puromycin (determine optimal concentration for {cell_line}, typically 1-3 μg/mL)

### Transfection
- Lipofectamine 3000 or PEI
- Polybrene (8 μg/mL for transduction)

## Protocol

### Day -1: gRNA Cloning
1. Anneal gRNA oligos:
   - Mix 1 μL each oligo (100 μM) + 1 μL T4 Ligase Buffer + 7 μL H₂O
   - Heat to 95°C for 5 min, ramp down to 25°C at 0.1°C/sec
2. Digest vector with BsmBI at 37°C for 1 hour
3. Ligate annealed oligos into digested vector
4. Transform into Stbl3 competent cells (important for lentiviral constructs)
5. Colony PCR and sequence verify

### Day 0: Lentiviral Packaging (HEK293T)
1. Seed HEK293T at 4×10⁶ cells in 10 cm dish
2. Next day (70% confluence), transfect:
   - 10 μg lentiCRISPRv2-{gene}
   - 7.5 μg psPAX2
   - 2.5 μg pMD2.G
   - Use Lipofectamine 3000 per manufacturer protocol
3. Change media after 6-8 hours

### Day 2: Harvest Virus
1. Collect supernatant (first harvest)
2. Add fresh media
3. Filter through 0.45 μm filter
4. Store at 4°C (use within 1 week) or aliquot at -80°C

### Day 3: Second Harvest + Transduction
1. Collect second supernatant, filter
2. Pool with first harvest
3. Seed {cell_line} at 30-40% confluence in 6-well plate
4. Add 1 mL viral supernatant + 8 μg/mL polybrene
5. Spinfection: 800×g for 60 min at 32°C (optional but improves efficiency)

### Day 4: Selection
1. Replace media with fresh complete media + puromycin
2. Include uninfected control well
3. Maintain selection until control cells are dead (typically 3-5 days)

### Day 7-10: Validation
1. **Western Blot:** Confirm {gene} protein loss
2. **Genomic PCR + Sanger Sequencing:** Confirm indels at target site
3. **T7 Endonuclease I Assay:** Estimate editing efficiency

## Critical Notes

⚠️ **For {cell_line}:**
- Verify optimal puromycin concentration with kill curve first
- Some cell lines may require MOI optimization
- Check doubling time to plan experiments

⚠️ **Controls:**
- Non-targeting control gRNA (Addgene #80263)
- Uninfected cells for selection
- Consider rescue experiment for validation

## Expected Results

- Knockout efficiency: 70-90% (bulk population)
- Protein depletion visible by Day 5-7 post-selection
- For complete KO, consider single-cell cloning

## Troubleshooting

| Issue | Possible Cause | Solution |
|-------|---------------|----------|
| Low viral titer | Poor transfection | Use fresh PEI/Lipofectamine, check HEK293T passage |
| No knockout | Poor gRNA | Try alternative gRNAs from table |
| Cells dying without selection | Toxic target | Use inducible Cas9 system |
| Incomplete KO | Multiple alleles | Single-cell clone and genotype |
"""

    async def _generate_western_protocol(
        self, gene: str, cell_line: str, use_llm: bool
    ) -> Dict:
        """Generate Western Blot protocol."""

        if use_llm and (self.openai_key or self.anthropic_key):
            content = await self._llm_generate_protocol("Western Blot", gene, cell_line)
        else:
            content = self._western_template(gene, cell_line)

        return {
            "title": f"Western Blot Analysis of {gene} in {cell_line}",
            "type": "western",
            "content": content or self._western_template(gene, cell_line),
            "reagents": self._get_western_reagents(gene),
            "timeline": "2 days",
            "generated_by": "LLM"
            if (use_llm and content and (self.openai_key or self.anthropic_key))
            else "Template",
        }

    def _western_template(self, gene: str, cell_line: str) -> str:
        return f"""# Western Blot: {gene} Expression in {cell_line}

**Objective:** Detect and quantify {gene} protein expression.

## Materials
- RIPA lysis buffer + protease/phosphatase inhibitors
- BCA Protein Assay Kit
- 4-12% Bis-Tris gel
- PVDF membrane (0.45 μm)
- Primary antibody: Anti-{gene} (verify source and dilution)
- Loading control: Anti-β-Actin or Anti-GAPDH
- HRP-conjugated secondary antibody
- ECL substrate

## Protocol

### Sample Preparation
1. Wash {cell_line} cells with cold PBS
2. Lyse in RIPA buffer (100 μL per 10⁶ cells) + inhibitors
3. Incubate on ice 30 min, vortex every 10 min
4. Centrifuge 14,000×g, 15 min, 4°C
5. Transfer supernatant, quantify by BCA

### Gel Electrophoresis
1. Load 20-30 μg protein per lane
2. Run at 120V for 90 min (until dye front exits)

### Transfer
1. Activate PVDF in methanol
2. Wet transfer: 100V, 60 min, 4°C (or overnight at 30V)
3. Confirm transfer with Ponceau S staining

### Immunoblotting
1. Block: 5% milk/TBST, 1 hour RT
2. Primary: Anti-{gene} (optimize dilution), overnight 4°C
3. Wash: 3× TBST, 10 min each
4. Secondary: HRP-conjugated, 1:5000, 1 hour RT
5. Wash: 3× TBST
6. Develop with ECL, image

## Expected Results
- {gene} band at expected molecular weight
- Compare to loading control for normalization
"""

    async def _generate_drug_assay_protocol(
        self, gene: str, cell_line: str, use_llm: bool
    ) -> Dict:
        """Generate drug sensitivity assay protocol."""

        content = self._drug_assay_template(gene, cell_line)

        return {
            "title": f"Drug Sensitivity Assay: {gene} Inhibition in {cell_line}",
            "type": "drug_assay",
            "content": content,
            "reagents": ["CellTiter-Glo", "96-well white plates", "Target inhibitor"],
            "timeline": "4 days",
            "generated_by": "Template",
        }

    def _drug_assay_template(self, gene: str, cell_line: str) -> str:
        return f"""# IC50 Determination: {gene} Inhibitor in {cell_line}

**Objective:** Determine sensitivity of {cell_line} to {gene}-targeting compounds.

## Protocol

### Day 0: Seeding
1. Seed {cell_line} at 2,000-5,000 cells/well in 96-well white plates
2. Allow to attach overnight

### Day 1: Treatment
1. Prepare 8-point serial dilution of compound (3-fold or half-log)
2. Typical range: 10 μM to 1 nM
3. Add compound in triplicate
4. Include DMSO vehicle control

### Day 4: Readout
1. Equilibrate CellTiter-Glo to RT
2. Add 100 μL reagent per well
3. Shake 2 min, incubate 10 min
4. Read luminescence

### Analysis
1. Normalize to DMSO control (100%)
2. Fit 4-parameter dose-response curve
3. Calculate IC50 using GraphPad Prism or similar

## Controls
- DMSO vehicle
- Positive control (known cytotoxic agent)
- Media-only background
"""

    async def _generate_rnai_protocol(
        self, gene: str, cell_line: str, use_llm: bool
    ) -> Dict:
        """Generate RNAi knockdown protocol."""

        content = f"""# siRNA Knockdown of {gene} in {cell_line}

**Objective:** Transient knockdown of {gene} using siRNA.

## Materials
- siRNA targeting {gene} (pool of 4 siRNAs recommended, e.g., Dharmacon SMARTpool)
- Non-targeting control siRNA
- Lipofectamine RNAiMAX
- Opti-MEM

## Protocol

### Day 0: Seeding
1. Seed {cell_line} at 50-60% confluence in 6-well plates
2. Use antibiotic-free media

### Day 1: Transfection
1. Per well:
   - Tube A: 25 pmol siRNA + 150 μL Opti-MEM
   - Tube B: 7.5 μL RNAiMAX + 150 μL Opti-MEM
2. Incubate 5 min separately
3. Combine A+B, incubate 20 min
4. Add dropwise to cells

### Day 2-4: Analysis
- **48h:** Optimal for mRNA knockdown (qPCR)
- **72h:** Optimal for protein knockdown (Western)

## Expected Results
- 70-90% knockdown at mRNA level
- 50-80% reduction at protein level

## Controls
- Non-targeting siRNA (same concentration)
- Mock transfection (reagent only)
- Untreated cells
"""

        return {
            "title": f"siRNA Knockdown of {gene} in {cell_line}",
            "type": "rnai",
            "content": content,
            "reagents": ["siRNA pool", "RNAiMAX", "Opti-MEM"],
            "timeline": "3-4 days",
            "generated_by": "Template",
        }

    async def _generate_if_protocol(
        self, gene: str, cell_line: str, use_llm: bool
    ) -> Dict:
        """Generate immunofluorescence protocol."""

        content = f"""# Immunofluorescence: {gene} Localization in {cell_line}

**Objective:** Visualize subcellular localization of {gene}.

## Protocol

### Fixation & Permeabilization
1. Seed {cell_line} on coverslips in 24-well plate
2. Fix: 4% PFA, 15 min RT
3. Wash: 3× PBS
4. Permeabilize: 0.1% Triton X-100, 10 min
5. Wash: 3× PBS

### Immunostaining
1. Block: 5% BSA/PBS, 1 hour RT
2. Primary: Anti-{gene} in blocking buffer, overnight 4°C
3. Wash: 3× PBS, 5 min each
4. Secondary: Fluorophore-conjugated, 1 hour RT (protect from light)
5. Wash: 3× PBS
6. Counterstain: DAPI (1:1000), 5 min
7. Mount with antifade medium

### Imaging
- Confocal microscopy recommended
- Z-stack for 3D localization
- Include secondary-only control
"""

        return {
            "title": f"Immunofluorescence: {gene} in {cell_line}",
            "type": "immunofluorescence",
            "content": content,
            "reagents": [
                "Primary antibody",
                "Fluorescent secondary",
                "DAPI",
                "Mounting medium",
            ],
            "timeline": "2 days",
            "generated_by": "Template",
        }

    async def _generate_qpcr_protocol(
        self, gene: str, cell_line: str, use_llm: bool
    ) -> Dict:
        """Generate qPCR protocol."""

        content = f"""# RT-qPCR: {gene} Expression in {cell_line}

**Objective:** Quantify {gene} mRNA expression levels.

## Protocol

### RNA Extraction
1. Lyse {cell_line} cells in TRIzol (1 mL per 10⁶ cells)
2. Extract RNA per manufacturer protocol
3. DNase treat (recommended)
4. Quantify and assess quality (A260/280 > 1.8)

### cDNA Synthesis
1. Use 500 ng - 1 μg total RNA
2. Use high-capacity cDNA kit
3. Include no-RT control

### qPCR
1. Master mix per reaction:
   - 10 μL 2× SYBR Green mix
   - 1 μL forward primer (10 μM)
   - 1 μL reverse primer (10 μM)
   - 2 μL cDNA (1:5 diluted)
   - 6 μL H₂O
2. Run in triplicate
3. Include no-template control

### Primer Design
- Design primers spanning exon-exon junctions
- Product size: 80-150 bp
- Use NCBI Primer-BLAST or Primer3

### Analysis
1. Calculate ΔCt = Ct({gene}) - Ct(housekeeping)
2. Calculate ΔΔCt = ΔCt(treated) - ΔCt(control)
3. Fold change = 2^(-ΔΔCt)

## Housekeeping Genes
- GAPDH, ACTB, or RPL13A (validate for {cell_line})
"""

        return {
            "title": f"RT-qPCR: {gene} Expression",
            "type": "qpcr",
            "content": content,
            "reagents": ["TRIzol", "cDNA kit", "SYBR Green", "Primers"],
            "timeline": "1-2 days",
            "generated_by": "Template",
        }

    async def _generate_general_protocol(
        self, method: str, gene: str, cell_line: str, use_llm: bool
    ) -> Dict:
        """Generate generic protocol."""

        return {
            "title": f"{method}: {gene} in {cell_line}",
            "type": "general",
            "content": f"""# {method} Protocol for {gene} in {cell_line}

**Target Gene:** {gene}
**Cell Line:** {cell_line}
**Method:** {method}

Please consult published literature for detailed protocols specific to this assay type.

## General Considerations
1. Verify {cell_line} growth conditions
2. Confirm reagent compatibility
3. Include appropriate controls
4. Consider biological replicates (n≥3)
""",
            "reagents": [],
            "timeline": "Variable",
            "generated_by": "Template",
        }

    def _get_crispr_reagents(self, cell_line: str) -> List[Dict]:
        """Get CRISPR reagent list with sources."""
        return [
            {
                "name": "lentiCRISPRv2",
                "source": "Addgene #52961",
                "notes": "Contains Cas9 + gRNA scaffold",
            },
            {
                "name": "psPAX2",
                "source": "Addgene #12260",
                "notes": "Packaging plasmid",
            },
            {"name": "pMD2.G", "source": "Addgene #12259", "notes": "VSV-G envelope"},
            {
                "name": "Puromycin",
                "source": "Gibco A1113802",
                "notes": f"Optimize for {cell_line}",
            },
            {"name": "Polybrene", "source": "Sigma TR-1003", "notes": "8 μg/mL final"},
        ]

    def _get_western_reagents(self, gene: str) -> List[Dict]:
        """Get Western blot reagent list."""
        return [
            {
                "name": f"Anti-{gene}",
                "source": "Verify in CiteAb",
                "notes": "Check validated applications",
            },
            {
                "name": "Anti-β-Actin",
                "source": "Sigma A5441",
                "notes": "Loading control",
            },
            {"name": "HRP-anti-mouse IgG", "source": "CST 7076", "notes": "1:5000"},
            {"name": "HRP-anti-rabbit IgG", "source": "CST 7074", "notes": "1:5000"},
        ]

    def _get_crispr_timeline(self) -> List[Dict]:
        """Get CRISPR experiment timeline."""
        return [
            {"day": -1, "task": "Clone gRNA into vector"},
            {"day": 0, "task": "Transfect HEK293T for virus production"},
            {"day": 2, "task": "First viral harvest"},
            {"day": 3, "task": "Second harvest + transduce target cells"},
            {"day": 4, "task": "Begin puromycin selection"},
            {"day": 7, "task": "Selection complete, expand cells"},
            {"day": 10, "task": "Validate knockout (WB, sequencing)"},
        ]
