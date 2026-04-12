import { useRef, useEffect, useCallback, useMemo } from 'react'
import { EditorView, keymap, lineNumbers, highlightActiveLine, drawSelection } from '@codemirror/view'
import { EditorState, Compartment } from '@codemirror/state'
import { json } from '@codemirror/lang-json'
import { indentWithTab } from '@codemirror/commands'
import { syntaxHighlighting, defaultHighlightStyle } from '@codemirror/language'

/**
 * Minimal CM6 wrapper that matches the playground's visual style.
 *
 * Props:
 *   value: string
 *   onChange: (value: string) => void
 *   language: 'json' | 'plain'
 *   onEditorReady: (scrollToLine: (n) => void) => void
 *   className: string (container className)
 */
export default function CodeEditor({ value, onChange, language = 'json', onEditorReady, className }) {
  const containerRef = useRef(null)
  const viewRef = useRef(null)
  const onChangeRef = useRef(onChange)
  const suppressNextUpdate = useRef(false)

  // Keep onChange ref fresh without recreating editor
  useEffect(() => { onChangeRef.current = onChange }, [onChange])

  // Custom theme matching the playground's design tokens
  const theme = useMemo(() => EditorView.theme({
    '&': {
      fontSize: '11px',
      fontFamily: "'JetBrains Mono', ui-monospace, monospace",
      backgroundColor: 'var(--color-panel)',
      height: '100%',
    },
    '.cm-content': {
      padding: '16px',
      lineHeight: '1.8',
      caretColor: 'var(--color-ink-2)',
    },
    '.cm-gutters': {
      backgroundColor: 'var(--color-panel)',
      borderRight: 'none',
      color: 'var(--color-muted)',
      fontSize: '10px',
      paddingLeft: '8px',
    },
    '.cm-activeLineGutter': {
      backgroundColor: 'transparent',
      color: 'var(--color-mid)',
    },
    '.cm-activeLine': {
      backgroundColor: 'rgba(0,0,0,0.02)',
    },
    '.cm-selectionBackground': {
      backgroundColor: 'rgba(139, 58, 42, 0.15) !important',
    },
    '&.cm-focused .cm-selectionBackground': {
      backgroundColor: 'rgba(139, 58, 42, 0.2) !important',
    },
    '.cm-cursor': {
      borderLeftColor: 'var(--color-ink-2)',
    },
    // Error highlight line decoration
    '.cm-error-highlight': {
      backgroundColor: 'rgba(158, 51, 32, 0.08)',
      transition: 'background-color 2s ease-out',
    },
    '.cm-error-highlight-fade': {
      backgroundColor: 'transparent',
    },
    '.cm-scroller': {
      overflow: 'auto',
    },
  }), [])

  // Create editor once
  useEffect(() => {
    if (!containerRef.current) return

    const languageCompartment = new Compartment()

    const extensions = [
      theme,
      lineNumbers(),
      highlightActiveLine(),
      drawSelection(),
      syntaxHighlighting(defaultHighlightStyle),
      keymap.of([indentWithTab]),
      EditorView.lineWrapping,
      languageCompartment.of(language === 'json' ? json() : []),
      EditorState.tabSize.of(2),
      EditorView.updateListener.of(update => {
        if (update.docChanged && !suppressNextUpdate.current) {
          onChangeRef.current(update.state.doc.toString())
        }
        suppressNextUpdate.current = false
      }),
    ]

    const state = EditorState.create({ doc: value, extensions })
    const view = new EditorView({ state, parent: containerRef.current })
    viewRef.current = view

    // Expose scrollToLine
    if (onEditorReady) {
      onEditorReady((lineNum) => {
        scrollToLine(view, lineNum)
      })
    }

    return () => {
      view.destroy()
      viewRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Mount once

  // Sync external value changes into CM6 (e.g., fixture switch)
  useEffect(() => {
    const view = viewRef.current
    if (!view) return
    const currentDoc = view.state.doc.toString()
    if (currentDoc !== value) {
      suppressNextUpdate.current = true
      view.dispatch({
        changes: { from: 0, to: currentDoc.length, insert: value },
      })
    }
  }, [value])

  return (
    <div ref={containerRef} className={className || 'w-full min-h-[520px]'} />
  )
}

/**
 * Scroll CM6 view to a 1-based line number and briefly highlight it.
 */
function scrollToLine(view, lineNum) {
  if (!view || !lineNum) return
  const doc = view.state.doc
  const clampedLine = Math.max(1, Math.min(lineNum, doc.lines))
  const line = doc.line(clampedLine)

  // Scroll into view
  view.dispatch({
    effects: EditorView.scrollIntoView(line.from, { y: 'center' }),
    selection: { anchor: line.from },
  })

  // Transient highlight via DOM class
  requestAnimationFrame(() => {
    const lineDOM = view.domAtPos(line.from)
    if (lineDOM && lineDOM.node) {
      let lineElement = lineDOM.node
      while (lineElement && !lineElement.classList?.contains('cm-line')) {
        lineElement = lineElement.parentElement
      }
      if (lineElement) {
        lineElement.classList.add('cm-error-highlight')
        setTimeout(() => {
          lineElement.classList.remove('cm-error-highlight')
          lineElement.classList.add('cm-error-highlight-fade')
          setTimeout(() => {
            lineElement.classList.remove('cm-error-highlight-fade')
          }, 2000)
        }, 2000)
      }
    }
  })
}
