from flask_assets import Environment, Bundle

assets = Environment()

css_all = Bundle(
    'css/core/base.css',
    'css/core/navigation.css',
    'css/components/forms.css',
    'css/components/tables.css',
    'css/components/modals.css',
    'css/core/responsive.css',
    filters='cssmin',
    output='css/packed.css'
)

assets.register('css_all', css_all)
