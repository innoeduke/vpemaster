
     document.addEventListener('DOMContentLoaded', function() {
         const pSelect = document.getElementById('pathway');
         const form = document.getElementById('speech-logs-filter-form');

         if (pSelect) {
             new CustomSelectAdapter(pSelect);
         }
     });
 
