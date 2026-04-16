export type ContributionKind = "panel" | "route" | "widget";

export interface PanelContribution {
  id: string;
  title: string;
  path: string;
  description?: string;
}

export interface RouteContribution {
  id: string;
  path: string;
  title: string;
}

export interface WidgetContribution {
  id: string;
  title: string;
  description?: string;
}

export interface FrontendContributionBundle {
  moduleId: string;
  panels?: PanelContribution[];
  routes?: RouteContribution[];
  widgets?: WidgetContribution[];
}