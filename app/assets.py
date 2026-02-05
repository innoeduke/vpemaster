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
    'css/components/meeting_filter.css',
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
    # Clubs CSS (modular structure)
    'css/pages/clubs/clubs-base.css',
    'css/pages/clubs/clubs-desktop.css',
    'css/pages/clubs/clubs-ipad.css',
    'css/pages/clubs/clubs-mobile.css',
    # Contacts CSS (modular structure)
    'css/pages/contacts/contacts-base.css',
    'css/pages/contacts/contacts-desktop.css',
    'css/pages/contacts/contacts-ipad.css',
    'css/pages/contacts/contacts-mobile.css',
    'css/pages/login.css',
    # Pathway Library CSS (modular structure)
    'css/pages/pathway_library/pathway_library-base.css',
    'css/pages/pathway_library/pathway_library-desktop.css',
    'css/pages/pathway_library/pathway_library-ipad.css',
    'css/pages/pathway_library/pathway_library-mobile.css',
    # Tools CSS (modular structure)
    'css/pages/tools/tools-base.css',
    'css/pages/tools/tools-desktop.css',
    'css/pages/tools/tools-ipad.css',
    'css/pages/tools/tools-mobile.css',
    # Settings CSS (modular structure)
    'css/pages/settings/settings-base.css',
    'css/pages/settings/settings-desktop.css',
    'css/pages/settings/settings-ipad.css',
    'css/pages/settings/settings-mobile.css',
    # Messages CSS (modular structure)
    'css/pages/messages/messages-base.css',
    'css/pages/messages/messages-desktop.css',
    'css/pages/messages/messages-ipad.css',
    'css/pages/messages/messages-mobile.css',
    # Speech Logs CSS (modular structure)
    'css/pages/speech_logs/speech_logs-base.css',
    'css/pages/speech_logs/speech_logs-desktop.css',
    'css/pages/speech_logs/speech_logs-ipad.css',
    'css/pages/speech_logs/speech_logs-mobile.css',
    # Profile CSS (modular structure)
    'css/pages/profile/profile-base.css',
    'css/pages/profile/profile-desktop.css',
    'css/pages/profile/profile-ipad.css',
    'css/pages/profile/profile-mobile.css',
    'css/core/responsive.css',
    filters='cssmin',
    output='css/packed.css'
)

assets.register('css_all', css_all)
