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
    'css/components/pagination.css',
    # Agenda CSS (modular structure)
    'css/pages/agenda/agenda-base.css',
    'css/pages/agenda/agenda-desktop.css',
    'css/pages/agenda/agenda-ipad.css',
    'css/pages/agenda/agenda-mobile.css',
    # Booking CSS (modular structure)
    'css/pages/booking/booking-base.css',
    'css/pages/booking/booking-desktop.css',
    'css/pages/booking/booking-ipad.css',
    'css/pages/booking/booking-mobile.css',
    # Voting CSS (modular structure)
    'css/pages/voting/voting-base.css',
    'css/pages/voting/voting-desktop.css',
    'css/pages/voting/voting-ipad.css',
    'css/pages/voting/voting-mobile.css',
    'css/pages/clubs.css',
    # Contacts CSS (modular structure)
    'css/pages/contacts/contacts-base.css',
    'css/pages/contacts/contacts-desktop.css',
    'css/pages/contacts/contacts-ipad.css',
    'css/pages/contacts/contacts-mobile.css',
    'css/pages/login.css',
    'css/pages/pathway_library.css',
    'css/pages/tools.css',
    'css/pages/settings.css',
    'css/pages/messages.css',
    'css/pages/speech_logs.css',
    'css/pages/profile.css',
    'css/core/responsive.css',
    filters='cssmin',
    output='css/packed.css'
)

assets.register('css_all', css_all)
