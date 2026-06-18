document.addEventListener('DOMContentLoaded', function () {
    const signUpLink = document.getElementById('sign-up-link');
    const usernameInput = document.getElementById('username');

    // Sign Up: pre-fill the register page with whatever the user has typed.
    // The link's href is a fallback; we override it at click time so the
    // current username value travels with the navigation.
    if (signUpLink && usernameInput) {
        signUpLink.addEventListener('click', function (e) {
            e.preventDefault();
            const username = usernameInput.value.trim();
            const base = window.LOGIN_REGISTER_URL;
            window.location.href = username
                ? base + "?username=" + encodeURIComponent(username)
                : base;
        });
    }
});