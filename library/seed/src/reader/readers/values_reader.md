# ValuesReader

Reads a single column of numbers and returns a one-dimensional numeric
form. Operators that measure one vector — `diversity_simpson`,
`numeric_gini_coefficient` — need this shape, and no other reader
produces it.

## Input

A text file where every non-empty line holds one number:

```
# PBMC 3k, total counts per cell (first ten cells)
counts
2334
3306
1851
866
847
1478
1534
1029
1070
1510
```

- One value per line is the normal case; `column` picks another column
  when the file carries extra fields.
- `header: true` skips a first line that does not parse as a number.
- Lines beginning with `comment` (default `#`) and blank lines are ignored.
- Separators may be spaces, tabs or commas.

## Output

A form with a single axis (`dims: ["value"]` by default), `float64`
values, `info.missing_code = NaN` and `info.n_values` set to the row
count. Labels follow the position (`0`, `1`, …) because a bare vector
carries no natural names.

## Extended names

`.values` and `.vals` are accepted.

## Parameter reference

| Name | Type | Default | Meaning |
| --- | --- | --- | --- |
| `header` | boolean | `false` | First row is a header, not a value |
| `comment` | string | `#` | Comment-line prefix |
| `column` | integer | `0` | Column holding the number |
