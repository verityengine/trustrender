#set page(paper: "us-letter", margin: 1in)
#set text(size: 12pt)

= {{ title }}

{{ body }}

{% if note %}
_Note: {{ note }}_
{% endif %}
