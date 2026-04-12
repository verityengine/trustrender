/**
 * Builds a Map<dotPath, {line, col, parentLine}> from a JSON string.
 *
 * Single-pass streaming tokenizer that tracks nesting context.
 * For "sender.email" -> {line: 5, col: 4, parentLine: 3}
 * For "items[1].description" -> {line: 12, col: 6, parentLine: 10}
 *
 * Performance: O(n) single pass. Target <50ms for 10k lines.
 */

export function buildPathIndex(jsonString) {
  const index = new Map()

  // State
  let pos = 0
  let line = 1
  let col = 0
  const len = jsonString.length

  // Path tracking: stack of {type: 'object'|'array', key, arrayIndex, line}
  const stack = []

  function currentPath() {
    const parts = []
    for (const frame of stack) {
      if (frame.type === 'object' && frame.key !== null) {
        parts.push(frame.key)
      } else if (frame.type === 'array') {
        parts.push(`[${frame.arrayIndex}]`)
      }
    }
    return parts.join('.').replace(/\.\[/g, '[')
  }

  function parentLine() {
    for (let i = stack.length - 1; i >= 0; i--) {
      if (stack[i].line !== undefined) return stack[i].line
    }
    return 1
  }

  function skipWhitespace() {
    while (pos < len) {
      const ch = jsonString[pos]
      if (ch === ' ' || ch === '\t' || ch === '\r') {
        pos++
        col++
      } else if (ch === '\n') {
        pos++
        line++
        col = 0
      } else {
        break
      }
    }
  }

  function readString() {
    // pos is at opening "
    const startLine = line
    const startCol = col
    pos++ // skip "
    col++
    let str = ''
    while (pos < len) {
      const ch = jsonString[pos]
      if (ch === '\\') {
        pos += 2
        col += 2
        // Handle escaped chars in string value (we don't need exact value for indexing)
        const esc = jsonString[pos - 1]
        if (esc === 'n' || esc === 'r' || esc === 't' || esc === '"' || esc === '\\' || esc === '/') {
          str += esc === 'n' ? '\n' : esc === 't' ? '\t' : esc
        } else if (esc === 'u') {
          pos += 4
          col += 4
        }
      } else if (ch === '"') {
        pos++
        col++
        return { value: str, line: startLine, col: startCol }
      } else if (ch === '\n') {
        str += ch
        pos++
        line++
        col = 0
      } else {
        str += ch
        pos++
        col++
      }
    }
    return { value: str, line: startLine, col: startCol }
  }

  function skipValue() {
    // Skip a JSON value without deep parsing (for scalars)
    skipWhitespace()
    if (pos >= len) return
    const ch = jsonString[pos]
    if (ch === '"') {
      readString()
    } else if (ch === '{') {
      parseObject()
    } else if (ch === '[') {
      parseArray()
    } else {
      // number, true, false, null
      while (pos < len && jsonString[pos] !== ',' && jsonString[pos] !== '}' && jsonString[pos] !== ']' && jsonString[pos] !== '\n' && jsonString[pos] !== ' ' && jsonString[pos] !== '\t' && jsonString[pos] !== '\r') {
        pos++
        col++
      }
    }
  }

  function parseObject() {
    // pos is at {
    const objLine = line
    pos++
    col++
    skipWhitespace()

    if (pos < len && jsonString[pos] === '}') {
      pos++
      col++
      return
    }

    while (pos < len) {
      skipWhitespace()
      if (pos >= len || jsonString[pos] === '}') {
        pos++
        col++
        return
      }

      // Read key
      if (jsonString[pos] !== '"') {
        // malformed - bail
        return
      }
      const key = readString()

      // Push frame
      stack.push({ type: 'object', key: key.value, line: objLine })

      // Record this path
      const path = currentPath()
      if (path) {
        index.set(path, { line: key.line, col: key.col, parentLine: objLine })
      }

      skipWhitespace()
      // skip colon
      if (pos < len && jsonString[pos] === ':') {
        pos++
        col++
      }

      skipWhitespace()

      // Parse value
      if (pos < len) {
        const ch = jsonString[pos]
        if (ch === '{') {
          parseObject()
        } else if (ch === '[') {
          parseArray()
        } else {
          skipValue()
        }
      }

      stack.pop()

      skipWhitespace()
      if (pos < len && jsonString[pos] === ',') {
        pos++
        col++
      }
    }
  }

  function parseArray() {
    // pos is at [
    const arrLine = line
    pos++
    col++
    skipWhitespace()

    if (pos < len && jsonString[pos] === ']') {
      pos++
      col++
      return
    }

    let idx = 0
    while (pos < len) {
      skipWhitespace()
      if (pos >= len || jsonString[pos] === ']') {
        pos++
        col++
        return
      }

      stack.push({ type: 'array', arrayIndex: idx, line: arrLine })

      // Record array element path
      const elemLine = line
      const path = currentPath()
      if (path) {
        index.set(path, { line: elemLine, col: col, parentLine: arrLine })
      }

      // Parse element value
      if (pos < len) {
        const ch = jsonString[pos]
        if (ch === '{') {
          parseObject()
        } else if (ch === '[') {
          parseArray()
        } else {
          skipValue()
        }
      }

      stack.pop()
      idx++

      skipWhitespace()
      if (pos < len && jsonString[pos] === ',') {
        pos++
        col++
      }
    }
  }

  // Entry point
  try {
    skipWhitespace()
    if (pos < len) {
      const ch = jsonString[pos]
      if (ch === '{') parseObject()
      else if (ch === '[') parseArray()
    }
  } catch {
    // On any error, return whatever we've built so far
  }

  return index
}

/**
 * Resolve a dot-path error to a line number in the JSON.
 * If the exact path exists, returns its line.
 * If not (missing field), walks up to find the closest parent.
 *
 * Returns: {line, isMissing} or null if completely unresolvable.
 */
export function resolvePathToLine(pathIndex, errorPath) {
  if (!pathIndex || !errorPath) return null

  // Direct hit
  const direct = pathIndex.get(errorPath)
  if (direct) {
    return { line: direct.line, col: direct.col, isMissing: false }
  }

  // Walk up the path: "sender.email" -> "sender"
  const segments = splitPath(errorPath)
  for (let i = segments.length - 1; i >= 0; i--) {
    const parentPath = segments.slice(0, i).join('.').replace(/\.\[/g, '[')
    if (!parentPath) continue
    const parent = pathIndex.get(parentPath)
    if (parent) {
      return { line: parent.line, col: parent.col, isMissing: true }
    }
  }

  return null
}

/**
 * Split a dot-path into segments, respecting array indices.
 * "items[1].description" -> ["items", "[1]", "description"]
 * "sender.email" -> ["sender", "email"]
 */
function splitPath(path) {
  const parts = []
  let current = ''
  for (let i = 0; i < path.length; i++) {
    const ch = path[i]
    if (ch === '.') {
      if (current) parts.push(current)
      current = ''
    } else if (ch === '[') {
      if (current) parts.push(current)
      current = '['
    } else if (ch === ']') {
      current += ']'
      parts.push(current)
      current = ''
    } else {
      current += ch
    }
  }
  if (current) parts.push(current)
  return parts
}
