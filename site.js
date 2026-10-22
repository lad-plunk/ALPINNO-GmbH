/* Shared ALPINNO navigation, existing consent and form behaviour. */
(() => {
"use strict";
const mobileNavigation = window.matchMedia("(max-width: 1120px)");
    const navigationMenu = document.querySelector(".nav-menu");

    const syncNavigation = () => {
      if (navigationMenu) navigationMenu.open = !mobileNavigation.matches;
    };

    syncNavigation();
    if (mobileNavigation.addEventListener) {
      mobileNavigation.addEventListener("change", syncNavigation);
    } else {
      mobileNavigation.addListener(syncNavigation);
    }
    document.querySelectorAll(".nav-links a").forEach((link) => {
      link.addEventListener("click", () => {
        if (mobileNavigation.matches) navigationMenu.open = false;
      });
    });

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const logoVideo = document.querySelector(".hero-logo-video");

    if (logoVideo && !reducedMotion.matches) {
      logoVideo.play().catch(() => {});
    }

    const handleMotionPreference = (event) => {
      if (logoVideo && event.matches) {
        logoVideo.pause();
        logoVideo.currentTime = 0;
      }
    };

    if (reducedMotion.addEventListener) {
      reducedMotion.addEventListener("change", handleMotionPreference);
    } else {
      reducedMotion.addListener(handleMotionPreference);
    }

    const analyticsMeasurementId = document.querySelector('meta[name="alpinno:ga4-measurement-id"]')?.content.trim();
    const analyticsConsent = document.querySelector("#analytics-consent");
    const analyticsAccept = document.querySelector("#analytics-accept");
    const analyticsDecline = document.querySelector("#analytics-decline");
    const analyticsClose = document.querySelector("#analytics-close");
    const analyticsSettings = document.querySelector("#analytics-settings");
    const analyticsPreferenceKey = "alpinno-analytics-consent";
    let analyticsConsentGranted = false;
    let analyticsLoaded = false;

    const analyticsIsConfigured = /^G-[A-Z0-9]+$/.test(analyticsMeasurementId || "");
    const loadGoogleAnalytics = () => {
      if (!analyticsIsConfigured || analyticsLoaded) return;
      analyticsLoaded = true;
      analyticsConsentGranted = true;
      window.dataLayer = window.dataLayer || [];
      window.gtag = window.gtag || function () {
        window.dataLayer.push(arguments);
      };
      window.gtag("consent", "default", {
        analytics_storage: "denied",
        ad_storage: "denied",
        ad_user_data: "denied",
        ad_personalization: "denied"
      });
      window.gtag("consent", "update", {
        analytics_storage: "granted",
        ad_storage: "denied",
        ad_user_data: "denied",
        ad_personalization: "denied"
      });
      window.gtag("js", new Date());
      window.gtag("config", analyticsMeasurementId, {
        anonymize_ip: true,
        allow_google_signals: false,
        allow_ad_personalization_signals: false
      });
      const analyticsScript = document.createElement("script");
      analyticsScript.async = true;
      analyticsScript.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(analyticsMeasurementId)}`;
      document.head.append(analyticsScript);
    };

    const setAnalyticsPreference = (allowed) => {
      localStorage.setItem(analyticsPreferenceKey, allowed ? "granted" : "denied");
      analyticsConsent.hidden = true;
      analyticsConsentGranted = allowed;
      if (allowed) {
        if (analyticsLoaded && window.gtag) {
          window.gtag("consent", "update", {
            analytics_storage: "granted",
            ad_storage: "denied",
            ad_user_data: "denied",
            ad_personalization: "denied"
          });
        } else {
          loadGoogleAnalytics();
        }
      } else if (window.gtag) {
        window.gtag("consent", "update", {
          analytics_storage: "denied",
          ad_storage: "denied",
          ad_user_data: "denied",
          ad_personalization: "denied"
        });
      }
    };

    if (analyticsIsConfigured) {
      const storedAnalyticsPreference = localStorage.getItem(analyticsPreferenceKey);
      if (storedAnalyticsPreference === "granted") {
        loadGoogleAnalytics();
      } else if (storedAnalyticsPreference !== "denied") {
        analyticsConsent.hidden = false;
      }
      analyticsAccept.addEventListener("click", () => setAnalyticsPreference(true));
      analyticsDecline.addEventListener("click", () => setAnalyticsPreference(false));
      analyticsClose.addEventListener("click", () => setAnalyticsPreference(false));
      analyticsSettings.addEventListener("click", () => {
        analyticsConsent.hidden = false;
        analyticsAccept.focus();
      });
    } else {
      if (analyticsSettings) analyticsSettings.hidden = true;
    }

    document.querySelectorAll(".contact-topic-link").forEach((link) => {
      link.addEventListener("click", () => {
        const topic = link.dataset.contactTopic;
        const option = Array.from(document.querySelectorAll('#contact-form select[name="topic"] option'))
          .find((item) => item.textContent === topic);
        if (option) option.selected = true;
      });
    });

    document.querySelectorAll("form[data-form-kind]").forEach((form) => {
      const status = form.querySelector(".form-status");
      const submitButton = form.querySelector('button[type="submit"]');

      form.addEventListener("submit", () => {
        submitButton.disabled = true;
        status.textContent = form.dataset.formKind === "contact"
          ? "Sending your enquiry…"
          : "Opening secure subscription confirmation…";
        if (analyticsConsentGranted && window.gtag) {
          window.gtag("event", form.dataset.formKind === "contact" ? "contact_form_submit" : "newsletter_signup");
        }
      });
    });

    if ("IntersectionObserver" in window) {
      const observedSections = new Set();
      const sectionObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting || observedSections.has(entry.target.id)) return;
          observedSections.add(entry.target.id);
          if (analyticsConsentGranted && window.gtag) {
            window.gtag("event", "section_view", { section_name: entry.target.id });
          }
        });
      }, { threshold: 0.55 });
      document.querySelectorAll("main > section[id]").forEach((section) => sectionObserver.observe(section));
    }

    // Keep previously shared homepage fragment links useful after the page split.
    if (document.body.dataset.sitePage === "home") {
      const legacyPages = {
        about: "about.html", founder: "about.html", services: "services.html",
        engagements: "services.html", "how-we-work": "services.html",
        AIdea: "aidea.html", "AIdea-workflow": "aidea.html", "AIdea-proof": "aidea.html",
        "deployment-section": "aidea.html", contact: "contact.html", "contact-form": "contact.html"
      };
      const followLegacyLink = () => {
        let id;
        try { id = decodeURIComponent(window.location.hash.slice(1)); } catch { return; }
        const page = legacyPages[id];
        if (page) window.location.replace(page + window.location.search + window.location.hash);
      };
      window.addEventListener("hashchange", followLegacyLink);
      followLegacyLink();
    }
    const requestedTopic = new URLSearchParams(window.location.search).get("topic");
    const topicSelect = document.querySelector('#contact-form select[name="topic"]');
    if (requestedTopic && topicSelect) {
      const option = Array.from(topicSelect.options).find(item => item.value === requestedTopic || item.textContent === requestedTopic);
      if (option) option.selected = true;
    }
    document.addEventListener("keydown", event => {
      if (event.key !== "Escape") return;
      document.querySelectorAll('.site-navigation details[open]').forEach(menu => {
        if (menu.classList.contains("nav-menu") && !mobileNavigation.matches) return;
        menu.open = false;
        menu.querySelector("summary")?.focus();
      });
    });

})();
