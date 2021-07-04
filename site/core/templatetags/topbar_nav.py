from django import template
from django.urls import reverse

register = template.Library()


class TopBardNav(template.Node):

    def render(self, context):
        request = context["request"]
        t = template.loader.get_template('topbar_nav.html')
        return t.render({}, request)


@register.tag()
def topbar_nav(parser, token):
    try:
        tag_name = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError(
            "%r tag requires a single argument" % token.contents.split()[0]
        )

    return TopBardNav()
