if (typeof window.TemplateManager !== 'undefined') {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            if (window.location.pathname.includes('/templates/edit')) {
                window.TemplateManager.initEditorPage();
            } else {
                window.TemplateManager.initListPage();
            }
        });
    } else {
        if (window.location.pathname.includes('/templates/edit')) {
            window.TemplateManager.initEditorPage();
        } else {
            window.TemplateManager.initListPage();
        }
    }
}