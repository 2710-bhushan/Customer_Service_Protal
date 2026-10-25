(function () {
  // Check local storage or default to light
  const storedTheme = localStorage.getItem('servicehub_theme') || 'light';
  document.documentElement.setAttribute('data-theme', storedTheme);

  window.addEventListener('DOMContentLoaded', () => {
    // Inject theme switcher UI elements if needed, or bind to existing buttons with id "theme-toggle"
    const toggleButtons = document.querySelectorAll('.theme-toggle-btn, #theme-toggle');
    
    const updateButtonIcons = (theme) => {
      toggleButtons.forEach(btn => {
        const icon = btn.querySelector('i');
        if (icon) {
          if (theme === 'dark') {
            icon.className = 'fas fa-sun';
          } else {
            icon.className = 'fas fa-moon';
          }
        }
      });
    };

    updateButtonIcons(storedTheme);

    toggleButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('servicehub_theme', newTheme);
        updateButtonIcons(newTheme);
      });
    });

    // --- MOBILE HEADER AND NAVIGATION DYNAMIC INJECTION ---
    const setupMobileHeader = () => {
      // If screen is wider than 900px, remove mobile header if it exists and return
      if (window.innerWidth > 900) {
        const existingHeader = document.querySelector('.mobile-header-bar');
        if (existingHeader) existingHeader.remove();
        const existingOverlay = document.querySelector('.sidebar-overlay');
        if (existingOverlay) existingOverlay.remove();
        return;
      }

      // If already set up, don't duplicate
      if (document.querySelector('.mobile-header-bar')) return;

      const path = window.location.pathname;
      
      // Determine page title dynamically
      let pageTitle = 'ServiceHub';
      const h1Element = document.querySelector('.main h1, .main-split h1, .container h1, h1');
      if (h1Element) {
        pageTitle = h1Element.textContent.replace(/⚡/g, '').trim();
      } else {
        const titleEl = document.querySelector('title');
        if (titleEl) {
          pageTitle = titleEl.textContent.split('–')[0].split('-')[0].trim();
        }
      }

      // Find the sidebar element if it exists on the page
      const sidebar = document.querySelector('.sidebar');
      const isDashboardRoot = path === '/bookservice/' || path === '/employeeservicebooked/' || path === '/aadmin/' || path === '/servicebooked/' || path === '/admin/wallet/';

      // Create mobile header bar
      const headerBar = document.createElement('div');
      headerBar.className = 'mobile-header-bar';

      // Left container
      const leftDiv = document.createElement('div');
      leftDiv.className = 'mobile-header-left';

      // Create Sidebar Overlay if sidebar exists
      let overlay = null;
      if (sidebar) {
        overlay = document.createElement('div');
        overlay.className = 'sidebar-overlay';
        document.body.appendChild(overlay);

        overlay.onclick = () => {
          sidebar.classList.remove('active');
          overlay.classList.remove('active');
        };

        // Close sidebar on link click
        sidebar.querySelectorAll('a').forEach(link => {
          link.addEventListener('click', () => {
            sidebar.classList.remove('active');
            overlay.classList.remove('active');
          });
        });
      }

      if (isDashboardRoot && sidebar) {
        // Hamburger Menu Button for dashboard roots with a sidebar
        const menuBtn = document.createElement('button');
        menuBtn.className = 'mobile-header-btn';
        menuBtn.innerHTML = '<i class="fas fa-bars"></i>';
        menuBtn.setAttribute('aria-label', 'Toggle Menu');
        menuBtn.onclick = (e) => {
          e.stopPropagation();
          sidebar.classList.toggle('active');
          if (overlay) overlay.classList.toggle('active');
        };
        leftDiv.appendChild(menuBtn);
      } else if (path !== '/' && path !== '/signin/' && path !== '/signup/') {
        // Back Button for other sub-pages/panels
        const backBtn = document.createElement('button');
        backBtn.className = 'mobile-header-btn';
        backBtn.innerHTML = '<i class="fas fa-arrow-left"></i>';
        backBtn.setAttribute('aria-label', 'Go Back');
        
        // Smart fallbacks if history doesn't exist
        let fallbackUrl = '/bookservice/';
        if (path.includes('admin') || path.startsWith('/aadmin')) {
          fallbackUrl = '/aadmin/';
        } else if (path.includes('employee') || path.startsWith('/agent')) {
          fallbackUrl = '/employeeservicebooked/';
        }
        
        backBtn.onclick = () => {
          if (window.history.length > 1) {
            window.history.back();
          } else {
            window.location.href = fallbackUrl;
          }
        };
        leftDiv.appendChild(backBtn);
      } else if (sidebar) {
        // Hamburger fallback if sidebar exists on other pages
        const menuBtn = document.createElement('button');
        menuBtn.className = 'mobile-header-btn';
        menuBtn.innerHTML = '<i class="fas fa-bars"></i>';
        menuBtn.onclick = (e) => {
          e.stopPropagation();
          sidebar.classList.toggle('active');
          if (overlay) overlay.classList.toggle('active');
        };
        leftDiv.appendChild(menuBtn);
      }

      // Center container (Page Title)
      const centerDiv = document.createElement('div');
      centerDiv.className = 'mobile-header-center';
      centerDiv.textContent = pageTitle;

      // Right container
      const rightDiv = document.createElement('div');
      rightDiv.className = 'mobile-header-right';

      // Theme toggle inside mobile header
      const mobThemeBtn = document.createElement('button');
      mobThemeBtn.className = 'mobile-header-btn theme-toggle-btn';
      const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
      mobThemeBtn.innerHTML = currentTheme === 'dark' ? '<i class="fas fa-sun"></i>' : '<i class="fas fa-moon"></i>';
      mobThemeBtn.onclick = () => {
        const theme = document.documentElement.getAttribute('data-theme') || 'light';
        const newTheme = theme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('servicehub_theme', newTheme);
        
        // Update all theme toggle button icons on the page
        const icons = document.querySelectorAll('.theme-toggle-btn i, #theme-toggle i');
        icons.forEach(i => {
          i.className = newTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        });
      };
      rightDiv.appendChild(mobThemeBtn);

      // Assemble
      headerBar.appendChild(leftDiv);
      headerBar.appendChild(centerDiv);
      headerBar.appendChild(rightDiv);

      // Inject at the top of the body
      document.body.insertBefore(headerBar, document.body.firstChild);
    };

    // Run setup and bind to resize event
    setupMobileHeader();
    
    let resizeTimeout;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(setupMobileHeader, 100);
    });
  });
})();
