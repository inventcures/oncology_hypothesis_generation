// =============================================================================
// Shared Type Definitions for Onco-TTT Frontend
// =============================================================================

// --- Evidence & Hypotheses ---

export type EvidenceItem = {
  type: string;
  source?: string;
  target?: string;
  relation?: string;
  weight?: number;
  title?: string;
};

export type Hypothesis = {
  id: string;
  title: string;
  description: string;
  confidence: number;
  verified: boolean;
  novelty_score: number;
  evidence?: EvidenceItem[];
};

// --- Knowledge Graph ---

export type GraphNode = {
  id: string;
  type: string;
  label: string;
  color: string;
  border_color: string;
  confidence: number;
  radius: number;
  x: number;
  y: number;
  degree: number;
  source: string;
  glow: boolean;
  relevance?: number;
  signal_role?: "upstream" | "downstream" | "target";
};

export type GraphLink = {
  source: string;
  target: string;
  relation: string;
  label: string;
  weight: number;
  color: string;
  thickness: number;
  source_data: string;
  animated: boolean;
  signal_direction?: "upstream" | "downstream";
};

export type GraphLegendItem = {
  type: string;
  color: string;
  count: number;
  label: string;
};

export type GraphStats = {
  total_nodes: number;
  total_edges: number;
  entity_types: Record<string, number>;
  relation_types: Record<string, number>;
  sources: Record<string, number>;
};

export type GraphData = {
  nodes: GraphNode[];
  links: GraphLink[];
  stats?: GraphStats;
  legend?: GraphLegendItem[];
};

// --- Literature ---

export type Paper = {
  id: string;
  title: string;
  abstract: string;
  authors: string;
  year: number;
  citations: number;
  journal: string;
  url: string;
  source: string;
};

// --- Structure / Deep Research ---

export type PocketData = {
  id: string;
  name: string;
  color: string;
  center: number[];
  residue_ids: number[];
  druggability_score: number;
  druggability_label: string;
};

export type MutationAnalysis = {
  found: boolean;
  position?: number;
  wt_aa?: string;
  mut_aa?: string;
  coordinate?: number[];
  in_binding_pocket?: boolean;
  impact_assessment?: string;
  impact_score?: number;
  message?: string;
};

export type StructureResult = {
  uniprot_id?: string;
  pdb_url?: string;
  pdb_content?: string;
  pockets?: PocketData[];
  druggability_score: number;
  binding_site_residues?: number[];
  mutation_analysis?: MutationAnalysis;
  analysis?: {
    residue_count: number;
    avg_plddt?: number;
    high_confidence_pct?: number;
  };
  error?: string;
};

export type PatentResult = {
  scooped_score: number;
  risk_color: string;
  risk_label: string;
  risk_assessment?: string;
  message?: string;
  total_hits?: number;
  recent_filings_5y?: number;
  google_patents_link: string;
  lens_link: string;
  top_competitors?: { name: string; count: number }[];
  heatmap?: { name: string; data: { year: string; count: number }[] }[];
  sample_patents?: { title: string; assignee: string; date: string }[];
};

export type ModelResult = {
  total_found?: number;
  top_pick?: {
    name: string;
    disease: string;
    match_score: number;
    mutation_match?: string;
    mutations?: string[];
  };
  recommendations?: ModelRecommendation[];
  avoid_list?: { name: string; problem_info?: { issue: string } }[];
  notes?: string[];
};

export type ModelRecommendation = {
  name: string;
  disease: string;
  match_score: number;
  mutation_match?: string;
  mutations?: string[];
};

export type ProtocolResult = {
  content: string;
  generated_by?: string;
  grnas?: {
    sequence: string;
    gc_content: number;
    score: number;
    off_target_risk: string;
  }[];
  timeline?: { day: number; task: string }[];
  reagents?: (string | { name: string })[];
};

export type DeepResearchData = {
  struct: StructureResult;
  patent: PatentResult;
  models: ModelResult;
  proto: ProtocolResult;
  target: string;
  mutation: string | null;
  tissue: string;
  query: string;
};

// --- Validation ---

export interface ValidationCheck {
  status: "pass" | "caution" | "fail" | "unknown";
  score: number;
  title: string;
  subtitle?: string;
  summary: string;
  metric?: {
    name: string;
    value: number | string;
    interpretation: string;
  };
  details?: Record<string, unknown>;
}

export interface ValidationData {
  gene: string;
  disease: string;
  overall_score: number;
  overall_status: string;
  checks: {
    essentiality: ValidationCheck;
    survival: ValidationCheck;
    toxicity: ValidationCheck;
    drugability: ValidationCheck;
    biomarker: ValidationCheck;
    competition: ValidationCheck;
  };
  synthesis: {
    text: string;
    generated_by: string;
    exportable: boolean;
  };
}

// --- Clinical Trials ---

export interface ClinicalTrial {
  nct_id: string;
  title: string;
  official_title: string;
  status: string;
  phase: string;
  sponsor: string;
  start_date: string;
  completion_date: string;
  enrollment: number;
  conditions: string[];
  interventions: { name: string; type: string }[];
  locations: { city: string; state: string; country: string }[];
  primary_outcomes: string[];
  summary: string;
  url: string;
}

export interface TrialsSummary {
  total_count: number;
  by_phase: Record<string, number>;
  by_status: Record<string, number>;
  top_sponsors: { name: string; count: number }[];
  top_interventions: { name: string; type: string; count: number }[];
  enrollment_total: number;
  year_distribution: Record<string, number>;
  top_countries: { country: string; count: number }[];
}

export interface ClinicalTrialsData {
  query: {
    gene: string;
    disease: string;
    status_filter: string;
    phase_filter: string;
  };
  summary: TrialsSummary;
  trials: ClinicalTrial[];
  source: "live" | "fallback";
}

// --- View Modes ---

export type ViewMode =
  | "graph"
  | "table"
  | "metrics"
  | "papers"
  | "pathway"
  | "validate"
  | "deep_research"
  | "trials"
  | "dossier"
  | "competitive";

// --- Query History ---

export type QueryHistoryItem = {
  text: string;
  time: number;
};

// --- Target Dossier ---

export interface DossierSection {
  title: string;
  status: "pending" | "loading" | "done" | "error";
  score?: number;
  data?: unknown;
}

export interface TargetDossier {
  target: string;
  disease: string;
  timestamp: number;
  go_no_go_score: number;
  sections: {
    target_profile: DossierSection;
    genetic_evidence: DossierSection;
    druggability: DossierSection;
    safety: DossierSection;
    competitive_landscape: DossierSection;
    experimental_path: DossierSection;
    literature: DossierSection;
  };
}

// --- Indication Expansion ---

export interface IndicationScore {
  disease: string;
  disease_id: string;
  overall_score: number;
  association_score: number;
  mutation_frequency?: number;
  trial_count?: number;
  competitive_density?: number;
}

// --- What-If Simulation ---

export interface PerturbationResult {
  target_node: string;
  perturbation_type: "inhibit" | "activate" | "knockout";
  affected_nodes: {
    id: string;
    label: string;
    type: string;
    effect: number; // -1 to 1, negative = downregulated
    distance: number; // hops from target
  }[];
  pathway_effects: {
    pathway: string;
    net_effect: number;
    description: string;
  }[];
}
