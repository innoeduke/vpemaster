
  function validateAvatar(input) {
    if (input.files && input.files.length > 0) {
      const file = input.files[0];
      const maxSize = 5 * 1024 * 1024; // 5MB
      if (file.size > maxSize) {
        alert('File is too large. Max size is 5MB.');
        input.value = ''; // Clear the input
        return;
      }
      input.form.submit();
    }
  }

  function openTab(evt, tabName) {
    var i, tabcontent, tablinks;

    // Hide all tab content
    tabcontent = document.getElementsByClassName("tab-content");
    for (i = 0; i < tabcontent.length; i++) {
      tabcontent[i].style.display = "none";
    }

    // Remove active class from all tab links
    tablinks = document.getElementsByClassName("nav-item");
    for (i = 0; i < tablinks.length; i++) {
      tablinks[i].className = tablinks[i].className.replace(" active", "");
    }

    // Show the specific tab content and add active class to the button
    document.getElementById(tabName).style.display = "block";
    if (evt) {
      evt.currentTarget.className += " active";
    } else {
      // Fallback if no event passed (manual trigger)
      document.getElementById('tab-' + tabName).className += " active";
    }

    // Update URL without reloading
    const url = new URL(window.location);
    if (tabName === 'reset-password') {
      url.searchParams.set('tab', 'password');
    } else {
      url.searchParams.delete('tab');
    }
    window.history.replaceState({}, '', url);
  }

  // Check URL parameters on load
  document.addEventListener("DOMContentLoaded", function () {
    const urlParams = new URLSearchParams(window.location.search);
    const tab = urlParams.get('tab');

    if (tab === 'password') {
      openTab(null, 'reset-password');
    }
    
    // Track changes for Update Profile button
    const profileForm = document.getElementById('profile-form');
    const updateBtn = document.getElementById('update-profile-btn');
    
    if (profileForm && updateBtn) {
      profileForm.addEventListener('input', function() {
        updateBtn.disabled = false;
      });
      
      // Also handle change for selects or other elements if necessary
      profileForm.addEventListener('change', function() {
        updateBtn.disabled = false;
      });

      profileForm.addEventListener('submit', function() {
        // Set a tiny timeout to ensure the form actually submits before disabling
        // This provides the "reset to initial state" feel before page reload
        setTimeout(() => {
          updateBtn.disabled = true;
        }, 50);
      });
    }
  });
