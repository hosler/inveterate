from django import template
from django.urls import reverse

register = template.Library()


class DashboardNav(template.Node):

    def render(self, context):
        urls = ['services']
        request = context["request"]
        if request.user.is_authenticated:
            t = template.loader.get_template('dashboard_nav.html')
            if request.user.is_staff:
                urls.extend(['plans',
                             'templates',
                             'pools',
                             'ips',
                             'nodes',
                             'node-disks',
                             'billing',
                             #'configs'
                             ])
            #context['var'] = request.user
            return t.render({"pages": urls}, request)
        else:
            return


@register.tag()
def dashboard_nav(parser, token):
    try:
        tag_name = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError(
            "%r tag requires a single argument" % token.contents.split()[0]
        )

    return DashboardNav()
