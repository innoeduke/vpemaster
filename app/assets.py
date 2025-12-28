from flask_assets import Environment, Bundle

assets = Environment()

css_all = Bundle(
    'css/core/base.css',
    'css/core/navigation.css',
    'css/components/forms.css',
    'css/components/tables.css',
    'css/components/modals.css',
    'css/components/autocomplete.css',
    'css/components/tabs.css',
    'css/pages/agenda.css',
    'css/pages/booking.css',
    'css/pages/contacts.css',
    'css/pages/login.css',
    'css/pages/pathway_library.css',
    'css/pages/roster.css',
    'css/pages/settings.css',
    'css/pages/speech_logs.css',
    'css/core/responsive.css',
    filters='cssmin',
    output='css/packed.css'
)

assets.register('css_all', css_all)
