from django import template

register = template.Library()


class Footer(template.Node):

    def render(self, context):
        request = context["request"]
        t = template.loader.get_template('footer.html')
        return t.render({}, request)


@register.tag()
def footer(parser, token):
    try:
        tag_name = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError(
            "%r tag requires a single argument" % token.contents.split()[0]
        )

    return Footer()
