# Templates & Escaping

Templates are Jinja2-preprocessed Typst files (`.j2.typ`). Jinja2 handles data binding; Typst handles layout and PDF generation.

```
{{ variable }}              Interpolate a value (auto-escaped)
{% for item in items %}     Loop
{% if condition %}          Conditional
{{ value | typst_money }}   Filter
```

Raw Typst files (`.typ`) are also supported but receive no data binding or escaping.

## Escaping

All string values interpolated via `{{ }}` are automatically escaped for Typst text/content contexts.

### Characters escaped

11 characters: `\` `$` `#` `@` `{` `}` `<` `` ` `` `~` `[` `]`

### Line-start markup

Characters that trigger Typst block markup at line start (`=` headings, `-` lists, `+` lists, `/` terms) are escaped via Unicode sequences when they appear at the start of a line in user data. Inline usage (dates, paths) is unaffected.

### Intentionally not escaped

`_` and `*` — word-boundary emphasis. Escaping everywhere would damage normal text like `snake_case`.

### Not in scope

Code mode, math mode, and other context-sensitive Typst syntax. Templates that embed user data in those contexts require author discipline.

## Filters

| Filter | Purpose | Escaping |
|--------|---------|----------|
| `typst_money` | Color-wrap negative currency values | Escapes input, returns markup |
| `typst_color` | Wrap value in colored text | Escapes input, returns markup |
| `typst_markup` | Bypass auto-escaping | **Unsafe for user input** |

`typst_markup` exists for template authors who need to emit controlled Typst formatting. Never pass arbitrary user data through it.

## Template rules

Templates may format values, loop through rows, conditionally show blocks, and render precomputed strings. Templates must not perform business logic (currency calculation, tax computation, rounding). Those values should arrive precomputed in the data.
