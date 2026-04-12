/**
 * Resolves a ReadinessIssue to an editor location.
 *
 * Returns: { editor: 'data'|'template', line, isMissing, navigable } or null.
 */

import { resolvePathToLine } from './json-path-index.js'

/**
 * @param {object} issue - {stage, check, severity, path, message, line?}
 * @param {Map|null} pathIndex - from buildPathIndex()
 * @param {string|null} templateSource - raw template text (for fallback search)
 * @returns {{ editor: 'data'|'template', line: number, isMissing: boolean, navigable: boolean } | null}
 */
export function resolveErrorLocation(issue, pathIndex, templateSource) {
  if (!issue) return null

  // Data errors (payload stage)
  if (issue.stage === 'payload') {
    const resolved = resolvePathToLine(pathIndex, issue.path)
    if (resolved) {
      return {
        editor: 'data',
        line: resolved.line,
        isMissing: resolved.isMissing,
        navigable: true,
      }
    }
    return { editor: 'data', line: null, isMissing: false, navigable: false }
  }

  // Template errors
  if (issue.stage === 'template' || issue.stage === 'template_preprocess' ||
      issue.stage === 'compilation' || issue.stage === 'template_syntax') {

    // Backend provides line directly
    if (issue.line) {
      return {
        editor: 'template',
        line: issue.line,
        isMissing: false,
        navigable: true,
      }
    }

    // Parse "template.j2.typ:14" format from path
    const colonMatch = issue.path && issue.path.match(/:(\d+)$/)
    if (colonMatch) {
      return {
        editor: 'template',
        line: parseInt(colonMatch[1], 10),
        isMissing: false,
        navigable: true,
      }
    }

    // Not navigable
    return { editor: 'template', line: null, isMissing: false, navigable: false }
  }

  // Other stages (environment, compliance, semantic) - not editor-mappable
  return null
}
