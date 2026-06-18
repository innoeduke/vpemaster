
        document.addEventListener('DOMContentLoaded', () => {
          const flashes = document.querySelectorAll('.flash-messages .flash');
          flashes.forEach(flash => {
            setTimeout(() => {
              flash.style.opacity = '0';
              flash.style.transform = 'translateY(20px)';
              flash.addEventListener('transitionend', () => flash.remove());
            }, 3000);
          });
        });
      
