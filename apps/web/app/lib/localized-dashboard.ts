import type {
  ApplicationDashboard,
  ApplicationDashboardLocalizedSettingsField,
  ApplicationDashboardLocaleContent,
  ApplicationDashboardQuickAction,
  ApplicationSettingsField,
  ApplicationTaskTemplate,
} from "@yggdrasil/frontend-sdk";

import type { Locale } from "../i18n";

function localizedOptions(
  options: ApplicationSettingsField["options"],
  localized: ApplicationDashboardLocalizedSettingsField["options"],
): ApplicationSettingsField["options"] {
  if (!options || !localized) {
    return options;
  }

  return options.map((option) => ({
    ...option,
    ...localized.find((candidate) => candidate.value === option.value),
  }));
}

function localizedQuickActions(
  actions: ApplicationDashboardQuickAction[] | undefined,
  localized: ApplicationDashboardLocaleContent["quickActions"],
): ApplicationDashboardQuickAction[] | undefined {
  if (!actions || !localized) {
    return actions;
  }

  return actions.map((action) => ({
    ...action,
    ...localized.find((candidate) => candidate.href && candidate.href === action.href),
  }));
}

function localizedTaskTemplates(
  templates: ApplicationTaskTemplate[] | undefined,
  localized: ApplicationDashboardLocaleContent["taskTemplates"],
): ApplicationTaskTemplate[] | undefined {
  if (!templates || !localized) {
    return templates;
  }

  return templates.map((template) => ({
    ...template,
    ...localized.find((candidate) => candidate.id === template.id),
  }));
}

function localizedSettingsSchema(
  fields: ApplicationSettingsField[] | undefined,
  localized: ApplicationDashboardLocaleContent["settingsSchema"],
): ApplicationSettingsField[] | undefined {
  if (!fields || !localized) {
    return fields;
  }

  return fields.map((field) => {
    const localizedField = localized.find((candidate) => candidate.key === field.key);
    if (!localizedField) {
      return field;
    }
    return {
      ...field,
      ...localizedField,
      options: localizedOptions(field.options, localizedField.options),
    };
  });
}

/**
 * Resolves a dashboard's locale overlay without changing its runtime payload.
 * Older API responses without `locales` remain usable through the base fields.
 */
export function localizeDashboard(dashboard: ApplicationDashboard, locale: Locale): ApplicationDashboard {
  const localized = dashboard.locales?.[locale];
  if (!localized) {
    return dashboard;
  }

  const hero = dashboard.hero || localized.hero
    ? { ...dashboard.hero, ...localized.hero }
    : undefined;

  return {
    ...dashboard,
    hero,
    quickActions: localizedQuickActions(dashboard.quickActions, localized.quickActions),
    taskTemplates: localizedTaskTemplates(dashboard.taskTemplates, localized.taskTemplates),
    settingsSchema: localizedSettingsSchema(dashboard.settingsSchema, localized.settingsSchema),
  };
}
