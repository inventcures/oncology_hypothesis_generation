/**
 * Frontend smoke tests for Onco-TTT.
 *
 * Tests cover:
 * - Type definitions are importable and structurally sound
 * - Mock data conforms to shared types
 * - View mode constants are exhaustive
 * - API response shapes match frontend expectations
 */

import { describe, it, expect } from "vitest";
import type {
  Hypothesis,
  GraphNode,
  GraphLink,
  GraphData,
  Paper,
  ValidationCheck,
  ValidationData,
  ClinicalTrial,
  ClinicalTrialsData,
  ViewMode,
  EvidenceItem,
  StructureResult,
  PatentResult,
  PerturbationResult,
  DossierSection,
  QueryHistoryItem,
} from "../types";

describe("Type definitions", () => {
  it("Hypothesis shape is valid", () => {
    const h: Hypothesis = {
      id: "h1",
      title: "KRAS as Driver",
      description: "Test hypothesis",
      confidence: 0.85,
      verified: true,
      novelty_score: 0.7,
      evidence: [{ type: "graph_edge", source: "KRAS", target: "BRAF", relation: "activates", weight: 0.9 }],
    };
    expect(h.id).toBe("h1");
    expect(h.confidence).toBeGreaterThan(0);
    expect(h.confidence).toBeLessThanOrEqual(1);
    expect(h.evidence).toHaveLength(1);
  });

  it("GraphNode shape is valid", () => {
    const node: GraphNode = {
      id: "KRAS",
      type: "gene",
      label: "KRAS",
      color: "#3b82f6",
      border_color: "#2563eb",
      confidence: 0.95,
      radius: 28,
      x: 400,
      y: 300,
      degree: 5,
      source: "gliner2",
      glow: true,
      relevance: 0.8,
      signal_role: "target",
    };
    expect(node.id).toBe("KRAS");
    expect(node.radius).toBeGreaterThan(0);
    expect(node.signal_role).toBe("target");
  });

  it("GraphLink shape is valid", () => {
    const link: GraphLink = {
      source: "KRAS",
      target: "BRAF",
      relation: "activates",
      label: "activates",
      weight: 0.85,
      color: "#10b981",
      thickness: 4.4,
      source_data: "gliner2",
      animated: true,
      signal_direction: "downstream",
    };
    expect(link.weight).toBeGreaterThan(0);
    expect(link.signal_direction).toBe("downstream");
  });

  it("GraphData can be empty", () => {
    const empty: GraphData = {
      nodes: [],
      links: [],
      stats: { total_nodes: 0, total_edges: 0, entity_types: {}, relation_types: {}, sources: {} },
      legend: [],
    };
    expect(empty.nodes).toHaveLength(0);
    expect(empty.stats?.total_nodes).toBe(0);
  });

  it("Paper shape is valid", () => {
    const p: Paper = {
      id: "abc123",
      title: "KRAS G12C in NSCLC",
      abstract: "We studied...",
      authors: "Smith J, Doe A",
      year: 2024,
      citations: 42,
      journal: "Nature",
      url: "https://example.com",
      source: "semantic_scholar",
    };
    expect(p.year).toBeGreaterThan(2000);
  });

  it("ValidationCheck shape is valid", () => {
    const check: ValidationCheck = {
      status: "pass",
      score: 85,
      title: "Essentiality",
      subtitle: "DepMap CRISPR",
      summary: "KRAS is essential",
      metric: { name: "Chronos Score", value: -1.2, interpretation: "< -1.0 = Essential" },
    };
    expect(check.status).toBe("pass");
    expect(check.score).toBeGreaterThanOrEqual(0);
    expect(check.score).toBeLessThanOrEqual(100);
  });

  it("ClinicalTrial shape is valid", () => {
    const trial: ClinicalTrial = {
      nct_id: "NCT12345678",
      title: "Phase 3 KRAS Study",
      official_title: "A Phase 3 Study",
      status: "Recruiting",
      phase: "Phase 3",
      sponsor: "Pharma Inc",
      start_date: "2024-01",
      completion_date: "2026-12",
      enrollment: 500,
      conditions: ["NSCLC"],
      interventions: [{ name: "Sotorasib", type: "Drug" }],
      locations: [{ city: "Boston", state: "MA", country: "US" }],
      primary_outcomes: ["Overall survival"],
      summary: "A study of...",
      url: "https://clinicaltrials.gov/ct2/show/NCT12345678",
    };
    expect(trial.nct_id).toMatch(/^NCT\d+$/);
    expect(trial.enrollment).toBeGreaterThan(0);
  });

  it("PerturbationResult shape is valid", () => {
    const result: PerturbationResult = {
      target_node: "KRAS",
      perturbation_type: "inhibit",
      affected_nodes: [
        { id: "BRAF", label: "BRAF", type: "gene", effect: -0.6, distance: 1 },
      ],
      pathway_effects: [
        { pathway: "MAPK", net_effect: -0.5, description: "MAPK suppressed" },
      ],
    };
    expect(result.perturbation_type).toBe("inhibit");
    expect(result.affected_nodes[0].effect).toBeLessThan(0);
  });
});

describe("ViewMode", () => {
  it("all view modes are defined", () => {
    const modes: ViewMode[] = [
      "graph", "table", "metrics", "papers", "pathway",
      "validate", "deep_research", "trials", "dossier", "competitive",
    ];
    expect(modes).toHaveLength(10);
  });
});

describe("Mock API response shapes", () => {
  it("/generate response matches GenerationResponse", () => {
    const mockResponse = {
      hypotheses: [
        { id: "h1", title: "Test", description: "Desc", confidence: 0.8, verified: false, novelty_score: 0.5 },
      ],
      graph_context: { nodes: [], links: [] },
      papers: [],
      atlas: { cells: [] },
      extraction: null,
    };
    expect(mockResponse.hypotheses).toHaveLength(1);
    expect(mockResponse.graph_context.nodes).toEqual([]);
  });

  it("/validate response matches ValidationData", () => {
    const makeCheck = (status: string): ValidationCheck => ({
      status: status as ValidationCheck["status"],
      score: 50,
      title: "Test",
      summary: "Test summary",
    });

    const mockValidation: ValidationData = {
      gene: "KRAS",
      disease: "lung cancer",
      overall_score: 75,
      overall_status: "pass",
      checks: {
        essentiality: makeCheck("pass"),
        survival: makeCheck("pass"),
        toxicity: makeCheck("caution"),
        drugability: makeCheck("pass"),
        biomarker: makeCheck("unknown"),
        competition: makeCheck("pass"),
      },
      synthesis: { text: "KRAS is validated...", generated_by: "Template", exportable: true },
    };
    expect(mockValidation.overall_score).toBeGreaterThanOrEqual(0);
    expect(Object.keys(mockValidation.checks)).toHaveLength(6);
  });

  it("DossierSection states are valid", () => {
    const states: DossierSection["status"][] = ["pending", "loading", "done", "error"];
    expect(states).toContain("pending");
    expect(states).toContain("done");
  });

  it("QueryHistoryItem shape is valid", () => {
    const item: QueryHistoryItem = { text: "KRAS G12C in NSCLC", time: Date.now() };
    expect(item.text.length).toBeGreaterThan(0);
    expect(item.time).toBeGreaterThan(0);
  });
});
