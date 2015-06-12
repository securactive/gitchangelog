{{title}}
{{#title_chars}}={{/title_chars}}

{{#versions}}
{{label}}
{{#label_chars}}-{{/label_chars}}

{{#sections}}
{{#display_label}}
{{label}}
{{#label_chars}}~{{/label_chars}}

{{/display_label}}
{{#commits}}
- {{subject}} [{{author}}]

{{#body}}
{{body_indented}}

{{/body}}
{{/commits}}
{{/sections}}
{{/versions}}
