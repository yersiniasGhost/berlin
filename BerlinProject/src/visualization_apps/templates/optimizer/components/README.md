# Optimizer Template Components

This directory contains modular Jinja2 template components for the Optimizer Visualization page.

## Component Files

| File | Lines | Description |
|------|-------|-------------|
| `_file_selector.html` | 48 | File upload inputs for monitor/data/GA configs |
| `_config_editor.html` | 287 | Tabbed configuration editor (7 tabs) |
| `_control_panel.html` | 40 | Optimization control buttons and progress bar |
| `_charts_section.html` | 165 | All 6 charts in responsive grid layout |
| `_test_evaluations.html` | 38 | Test data performance comparison table |
| `_elite_modal.html` | 45 | Modal for selecting elite to send to replay |

## Usage

Include these components in your main template:

```jinja2
{% include 'optimizer/components/_file_selector.html' %}
{% include 'optimizer/components/_config_editor.html' %}
{% include 'optimizer/components/_control_panel.html' %}
{% include 'optimizer/components/_charts_section.html' %}
{% include 'optimizer/components/_test_evaluations.html' %}
{% include 'optimizer/components/_elite_modal.html' %}
```

## Benefits

- **Modularity**: Each component is self-contained and focused
- **Maintainability**: Easy to locate and modify specific sections
- **Reusability**: Components can be reused in other templates
- **Testing**: Individual components can be tested in isolation
- **Collaboration**: Reduces merge conflicts when multiple developers work on UI

## Related Files

- **CSS**: `src/visualization_apps/static/css/optimizer.css`
- **JavaScript**: `src/visualization_apps/static/js/optimizer-config.js`
- **Main Template**: `src/visualization_apps/templates/optimizer/main_refactored.html`
- **Documentation**: `claudedocs/20251103_optimizer_template_refactoring.md`

## Notes

- All components use Jinja2 syntax with `{# comments #}`
- Components are prefixed with `_` to indicate they are partials
- Original 2580-line template has been split into manageable pieces
- JavaScript refactoring is documented but not yet implemented
