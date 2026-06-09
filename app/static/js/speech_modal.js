// static/js/speech_modal.js

// --- Globals (from HTML) ---
// These are assumed to be defined in the HTML <script> tags:
// - allProjects, pathwayMap

// --- DOM Elements Cache ---
const modalElements = {
  modal: document.getElementById("speechEditModal"),
  form: document.getElementById("speechEditForm"),
  title: document.querySelector("#speechEditModal h2"),
  logId: document.getElementById("edit-log-id"),
  sessionType: document.getElementById("edit-session-type-title"),
  speechTitle: document.getElementById("edit-speech-title"),
  speechTitleLabel: document.querySelector('#edit-speech-title-label'),
  sessionOwner: document.getElementById("edit-session-owner"),
  credential: document.getElementById("edit-credential"),
  mediaUrl: document.getElementById("edit-speech-media-url"),

  standardSelection: document.getElementById("standard-selection"),
  standardProjectFields: document.querySelector("#speech-mode-fields .sem-standard-project-fields"),

  projectModeFields: document.querySelector("#speech-mode-fields #project-mode-fields"),
  pathwayGenericRow: document.querySelector("#speech-mode-fields #pathway-generic-row"),
  pathwaySelect: document.querySelector("#speech-mode-fields #edit-pathway"),
  isProjectCheckbox: document.querySelector("#speech-mode-fields #edit-is-project"),
  levelSelectGroup: document.querySelector("#speech-mode-fields #level-select-group"),
  levelSelect: document.querySelector("#speech-mode-fields #edit-level"),
  projectSelectGroup: document.querySelector("#speech-mode-fields #project-select-group"),
  projectSelect: document.querySelector("#speech-mode-fields #edit-project"),
  labelPathway: document.querySelector("#speech-mode-fields #label-pathway-series"),
  labelLevel: document.querySelector("#speech-mode-fields #label-level"),
  labelProject: document.querySelector("#speech-mode-fields #label-project-presentation"),
  projectGroup: document.querySelector("#speech-mode-fields #project-group"),
  isProjectChk: document.querySelector("#speech-mode-fields #is-project-chk"),
  projectSelectDropdown: document.querySelector("#speech-mode-fields #project-select-dropdown"),
  pathwayGroup: document.querySelector("#speech-mode-fields #pathway-group"),
  pathwaySelectDropdown: document.querySelector("#speech-mode-fields #pathway-select-dropdown"),
  levelGroup: document.querySelector("#speech-mode-fields #level-group"),
  levelSelectDropdown: document.querySelector("#speech-mode-fields #level-select-dropdown"),
  speechModeFields: document.getElementById("speech-mode-fields"),
  roleModeFields: document.getElementById("role-mode-fields"),
  roleNameDisplay: document.getElementById("role-name-display"),
  roleOwnersScroll: document.getElementById("role-owners-scroll"),
};

// --- Utility Functions ---

/**
 * Generic utility to populate a <select> dropdown.
 */
function populateDropdown(
  dropdown,
  items,
  { defaultOption, valueField, textField }
) {
  dropdown.innerHTML = `<option value="">${defaultOption}</option>`;
  items.forEach((item) => {
    dropdown.add(new Option(item[textField], item[valueField]));
  });
}

/**
 * Populates a <select> with <optgroup>s.
 * @param {HTMLSelectElement} dropdown
 * @param {Object} groupedData - { "Type": ["Item1", "Item2"] }
 */
function populateGroupedDropdown(dropdown, groupedData, { defaultOption }) {
  dropdown.innerHTML = `<option value="">${defaultOption}</option>`;
  for (const [groupLabel, items] of Object.entries(groupedData)) {
    const optgroup = document.createElement("optgroup");
    optgroup.label = groupLabel;
    items.forEach((item) => {
      // Handle both simple string lists and object lists (if needed in future)
      const value = typeof item === 'object' ? item.name : item;
      const text = typeof item === 'object' ? item.name : item;
      optgroup.appendChild(new Option(text, value));
    });
    dropdown.appendChild(optgroup);
  }
}

/**
 * Toggles the "Generic Speech" mode, hiding/showing pathway fields.
 */
function toggleGeneric(isGeneric) {
  const {
    pathwayGenericRow,
    levelSelectGroup,
    projectSelectGroup,
    pathwaySelect,
    levelSelect,
    projectSelect,
  } = modalElements;
  const display = isGeneric ? "none" : "block";
  if (pathwayGenericRow) pathwayGenericRow.style.display = "block";
  if (levelSelectGroup) levelSelectGroup.style.display = display;
  if (projectSelectGroup) projectSelectGroup.style.display = display;
  if (pathwaySelect) pathwaySelect.disabled = false;
  if (levelSelect) levelSelect.disabled = isGeneric;
  if (projectSelect) projectSelect.disabled = isGeneric;

  if (isGeneric) {
    if (levelSelect) levelSelect.value = "";
    if (projectSelect) {
      projectSelect.value = "";
      projectSelect.innerHTML = '<option value="">-- Select --</option>';
    }
  }
}
// --- Main Public Functions ---

/**
 * Build a single-owner picker for use inside a modal card.
 *
 * Renders a tag-style display of the current owner plus a search input.
 * When the user picks a contact, onChange is called with the new ownerId
 * (or null when the tag is removed).
 *
 * Returns { wrapper, getOwnerId, setOwnerId, focusSearch }.
 */
function createModalOwnerPicker({ initialOwnerId, contacts, onChange, placeholder = "Search members..." }) {
  const wrapper = document.createElement("div");
  wrapper.className = "modal-owner-picker";

  const tagContainer = document.createElement("div");
  tagContainer.className = "owners-tags-container";
  wrapper.appendChild(tagContainer);

  const searchContainer = document.createElement("div");
  searchContainer.className = "autocomplete-container";
  searchContainer.style.position = "relative";

  const searchInput = document.createElement("input");
  searchInput.type = "text";
  searchInput.className = "owner-search-input";
  searchInput.placeholder = placeholder;
  searchInput.autocomplete = "off";
  searchInput.setAttribute("aria-autocomplete", "list");
  searchInput.setAttribute("aria-expanded", "false");
  searchContainer.appendChild(searchInput);
  wrapper.appendChild(searchContainer);

  let currentOwnerId = initialOwnerId ? String(initialOwnerId) : "";
  let currentContact = currentOwnerId
    ? (contacts || []).find((c) => String(c.id) === currentOwnerId) || null
    : null;
  let activeIndex = -1;
  let openDropdown = null;

  const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));

  // The dropdown is portaled to document.body and positioned with
  // position:fixed so it can never be clipped by overflow:auto on any
  // scrollable ancestor (the modal's sem-body in particular).
  const positionDropdown = () => {
    if (!openDropdown) return;
    const rect = searchInput.getBoundingClientRect();
    openDropdown.style.position = "fixed";
    openDropdown.style.left = `${rect.left}px`;
    openDropdown.style.top = `${rect.bottom}px`;
    openDropdown.style.width = `${rect.width}px`;
    openDropdown.style.zIndex = "10000";
  };

  const buildSuggestionItems = (matches, val) => {
    matches.forEach((contact, idx) => {
      const item = document.createElement("div");
      item.setAttribute("role", "option");
      item.dataset.contactId = String(contact.id);
      if (val) {
        const upper = contact.Name.toUpperCase();
        const matchIdx = upper.indexOf(val.toUpperCase());
        if (matchIdx >= 0) {
          item.innerHTML =
            `${escapeHtml(contact.Name.slice(0, matchIdx))}` +
            `<strong>${escapeHtml(contact.Name.slice(matchIdx, matchIdx + val.length))}</strong>` +
            `${escapeHtml(contact.Name.slice(matchIdx + val.length))}`;
        } else {
          item.textContent = contact.Name;
        }
      } else {
        item.textContent = contact.Name;
      }
      item.addEventListener("mousedown", (e) => {
        // mousedown (not click) so we beat the input's blur handler
        e.preventDefault();
        choose(contact);
      });
      if (idx === 0) item.classList.add("autocomplete-active");
      openDropdown.appendChild(item);
    });
  };

  const open = () => {
    close();
    const val = searchInput.value.trim();
    const source = (contacts && contacts.length)
      ? contacts
      : (window.allContacts && window.allContacts.length ? window.allContacts : []);
    const matches = source
      .filter((c) => c.Name)
      .filter((c) => !val || c.Name.toUpperCase().includes(val.toUpperCase()))
      .filter((c) => String(c.id) !== currentOwnerId)
      .slice(0, 10);

    openDropdown = document.createElement("div");
    openDropdown.setAttribute("class", "autocomplete-items");
    openDropdown.setAttribute("role", "listbox");
    document.body.appendChild(openDropdown);

    if (matches.length === 0) {
      const empty = document.createElement("div");
      empty.className = "autocomplete-empty";
      empty.textContent = val
        ? `No matches for "${val}"`
        : (source.length === 0
            ? "Loading members… (open the Edit Details modal after the agenda has loaded)"
            : "No matches");
      openDropdown.appendChild(empty);
    } else {
      buildSuggestionItems(matches, val);
    }
    positionDropdown();
    activeIndex = matches.length > 0 ? 0 : -1;
    searchInput.setAttribute("aria-expanded", "true");
  };

  const close = () => {
    if (openDropdown && openDropdown.parentNode) {
      openDropdown.parentNode.removeChild(openDropdown);
    }
    openDropdown = null;
    activeIndex = -1;
    searchInput.setAttribute("aria-expanded", "false");
  };

  const updateActive = () => {
    if (!openDropdown) return;
    const items = openDropdown.querySelectorAll("div[role='option']");
    items.forEach((it, i) => {
      it.classList.toggle("autocomplete-active", i === activeIndex);
    });
    if (activeIndex >= 0 && items[activeIndex]) {
      items[activeIndex].scrollIntoView({ block: "nearest" });
    }
  };

  const choose = (contact) => {
    setOwnerId(contact.id, { silent: false });
    searchInput.value = "";
    close();
    searchInput.focus();
  };

  // Reposition the dropdown if the window or the modal scrolls while it's
  // open (page scroll, modal scroll, or window resize). Listeners stay for
  // the picker's lifetime — positionDropdown is a no-op when not open.
  const repositionHandler = () => positionDropdown();
  window.addEventListener("scroll", repositionHandler, true);
  window.addEventListener("resize", repositionHandler);

  searchInput.addEventListener("focus", () => open());
  searchInput.addEventListener("input", () => {
    if (!openDropdown) open();
    else {
      // Re-render with the new query
      const wasActive = activeIndex;
      close();
      open();
      activeIndex = wasActive;
      updateActive();
    }
  });
  searchInput.addEventListener("blur", () => {
    // Defer close so mousedown on a suggestion can fire first
    setTimeout(() => close(), 120);
  });
  searchInput.addEventListener("keydown", (e) => {
    if (!openDropdown) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        open();
        return;
      }
    }
    const items = openDropdown
      ? openDropdown.querySelectorAll("div[role='option']")
      : [];
    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeIndex = (activeIndex + 1) % Math.max(items.length, 1);
      updateActive();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activeIndex = (activeIndex - 1 + items.length) % Math.max(items.length, 1);
      updateActive();
    } else if (e.key === "Enter") {
      if (activeIndex >= 0 && items[activeIndex]) {
        e.preventDefault();
        const id = items[activeIndex].dataset.contactId;
        const contact = (contacts || []).find((c) => String(c.id) === id);
        if (contact) choose(contact);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      close();
      searchInput.blur();
    } else if (e.key === "Backspace" && !searchInput.value) {
      // Empty input + backspace removes the current owner
      if (currentOwnerId) {
        e.preventDefault();
        setOwnerId(null, { silent: false });
      }
    }
  });

  const renderTag = () => {
    tagContainer.innerHTML = "";
    tagContainer.style.display = currentContact ? "flex" : "none";

    if (!currentContact) return;

    const tag = document.createElement("div");
    tag.className = "owner-tag";
    const label = document.createElement("span");
    label.textContent = currentContact.Name;
    tag.appendChild(label);

    const removeBtn = document.createElement("span");
    removeBtn.className = "remove-tag";
    removeBtn.innerHTML = '<i class="fas fa-times"></i>';
    removeBtn.title = "Remove owner";
    removeBtn.addEventListener("mousedown", (e) => {
      e.preventDefault();
      setOwnerId(null, { silent: false });
    });
    tag.appendChild(removeBtn);

    tagContainer.appendChild(tag);
  };

  function setOwnerId(newId, { silent = false } = {}) {
    const newIdStr = newId ? String(newId) : "";
    if (newIdStr === currentOwnerId) return;
    currentOwnerId = newIdStr;
    currentContact = newIdStr
      ? (contacts || []).find((c) => String(c.id) === newIdStr) || null
      : null;
    renderTag();
    if (!silent && typeof onChange === "function") {
      onChange(currentOwnerId, currentContact);
    }
  }

  function getOwnerId() {
    return currentOwnerId;
  }

  function focusSearch() {
    searchInput.focus();
    open();
  }

  renderTag();

  return { wrapper, getOwnerId, setOwnerId, focusSearch };
}

// --- Main Public Functions ---

/**
 * Main entry point to open the speech or role edit details modal.
 */
async function openEditDetailsModal(
  logId,
  workingPath = null,
  sessionTypeTitle = null,
  nextProject = null
) {
  try {
    const response = await fetch(`/speech_log/details/${logId}`);
    const data = await response.json();
    if (!data.success) throw new Error(data.message || "Unknown error");

    const passedSessionType =
      data.log.session_type_title ||
      sessionTypeTitle ||
      document.querySelector(`tr[data-id="${logId}"]`)?.dataset.sessionTypeTitle;
    const currentSessionType = passedSessionType || "Pathway Speech";

    // Pick up any in-flight edit the user made on the agenda row before opening
    // the modal — otherwise we'd discard their unsaved typing and show the
    // server's stale value.
    const agendaRow = document.querySelector(`tr[data-id="${logId}"]`);
    if (agendaRow) {
      const editTitleCell = agendaRow.querySelector('td[data-field="Session_Title"]');
      if (editTitleCell) {
        const ctl = editTitleCell.querySelector("input, select, span");
        if (ctl) {
          const liveValue = ctl.tagName === "SPAN" ? ctl.textContent : ctl.value;
          if (liveValue !== undefined && liveValue !== null) {
            data.log.Session_Title = liveValue;
          }
        }
      }
    }

    // Setup basic details
    resetModal(data.log, currentSessionType);

    const sessionType = currentSessionType;
    const isPreparedSpeech = sessionType === "Prepared Speech" || sessionType === "Pathway Speech" || sessionType === "Presentation";
    const isProjectRole = ["Topicsmaster", "Moderator", "Keynote Speaker", "Individual Evaluator", "Evaluation"].includes(data.log.role);

    const row = document.querySelector(`tr[data-id="${logId}"]`);

    if (!isPreparedSpeech && !isProjectRole) {
      // Toggle wrappers: show role mode, hide speech mode
      modalElements.speechModeFields.style.display = "none";
      modalElements.roleModeFields.style.display = "block";
      // The speech_title field is hidden in role mode, so the browser's
      // HTML5 validation can't focus it. Strip `required` so Save works.
      if (modalElements.speechTitle) modalElements.speechTitle.required = false;

      const roleName = data.log.role || (row ? row.dataset.role : "") || "N/A";
      modalElements.roleNameDisplay.textContent = roleName;

      // Get all owner IDs for this log
      let ownerIds = data.log.owner_ids || [];
      if (ownerIds.length === 0 && row) {
        try {
          ownerIds = JSON.parse(row.dataset.ownerIds || "[]");
        } catch (e) {
          const singleId = row.dataset.ownerId;
          if (singleId) ownerIds = [singleId];
        }
        if (ownerIds.length === 0) {
          const singleId = row.dataset.ownerId;
          if (singleId) ownerIds = [singleId];
        }
      }

      // Parse existing per-owner targets if available
      let existingOwnerTargets = data.log.owner_targets || {};
      if (Object.keys(existingOwnerTargets).length === 0 && row) {
        try {
          existingOwnerTargets = JSON.parse(row.dataset.ownerTargets || "{}");
        } catch (e) { /* ignore */ }
      }

      // Build the scrollable owner cards
      const scrollContainer = modalElements.roleOwnersScroll;
      scrollContainer.innerHTML = "";

      // Helper: build a pathway <select> with grouped options
      function buildPathwaySelect(ownerId) {
        const sel = document.createElement("select");
        sel.className = "role-card-pathway";
        sel.innerHTML = '';
        
        const contactsList = data.log.owners_data || window.allContacts || [];
        const contact = contactsList.find((c) => c.id == ownerId);
        let regPaths = [];
        if (contact && contact.registered_paths) {
          regPaths = contact.registered_paths.map(p => typeof p === 'object' ? p.name : p);
        }
        
        if (regPaths.length > 0) {
          sel.innerHTML = '<option value="">-- Select Pathway --</option>';
          regPaths.forEach((name) => {
            sel.appendChild(new Option(name, name));
          });
          if (!regPaths.includes("Non Pathway")) {
            sel.appendChild(new Option("Non Pathway", "Non Pathway"));
          }
        } else {
          sel.appendChild(new Option("Non Pathway", "Non Pathway"));
        }
        return sel;
      }

      // Helper: build a level <select>
      function buildLevelSelect() {
        const sel = document.createElement("select");
        sel.className = "role-card-level";
        sel.innerHTML = '<option value="">-- Select Level --</option>';
        for (let i = 1; i <= 5; i++) {
          sel.appendChild(new Option(`Level ${i}`, i));
        }
        return sel;
      }

      // Helper: determine default pathway + level for an owner
      function getOwnerDefaults(ownerId) {
        let pathway = "";
        let level = "";

        // 1. Check per-owner saved target first
        const savedTarget = existingOwnerTargets[ownerId];
        if (savedTarget !== undefined && savedTarget !== null) {
          pathway = savedTarget.pathway || "Non Pathway";
          level = savedTarget.level || "";
        } else {
          // 2. Fallback to contact data (only if ownerId has no saved target)
          const contactsList = data.log.owners_data || window.allContacts || [];
          const contact = contactsList.find((c) => c.id == ownerId);
          if (contact) {
            if (contact.Type === "Guest" || !contact.Current_Path) {
              pathway = "Non Pathway";
            } else {
              pathway = contact.Current_Path;
            }
            const levelMatch = (contact.Credentials || "").match(/\d+/);
            if (levelMatch) {
              level = Math.min(parseInt(levelMatch[0], 10) + 1, 5).toString();
            } else {
              level = "1";
            }
          }
        }

        if (!pathway) pathway = "Non Pathway";
        if (pathway === "Non Pathway") {
          level = "";
        } else if (!level) {
          level = "1";
        }

        return { pathway, level };
      }

      // Create one card per owner
      const contactsList = data.log.owners_data || window.allContacts || [];

      // Build a single role-owner card with an owner picker. When the owner
      // changes via the picker, pathway/level dropdowns are rebuilt for the
      // new owner's registered paths and the saved/default target values.
      const buildRoleOwnerCard = (initialOwnerId) => {
        const card = document.createElement("div");
        card.className = "role-owner-card";
        card.dataset.ownerId = initialOwnerId || "";

        // Holder objects so the closures always reference the current
        // pathway/level <select> elements (they get rebuilt on owner change).
        const pathHolder = { el: buildPathwaySelect(initialOwnerId) };
        const levelHolder = { el: buildLevelSelect() };

        // Pathway group
        const pathGroup = document.createElement("div");
        pathGroup.className = "form-group";
        const pathLabel = document.createElement("label");
        pathLabel.textContent = "Pathway";
        pathGroup.appendChild(pathLabel);
        pathGroup.appendChild(pathHolder.el);
        card.appendChild(pathGroup);

        // Level group
        const levelGroup = document.createElement("div");
        levelGroup.className = "form-group";
        const levelLabel = document.createElement("label");
        levelLabel.textContent = "Level";
        levelGroup.appendChild(levelLabel);
        levelGroup.appendChild(levelHolder.el);
        card.appendChild(levelGroup);

        const syncLevel = () => {
          if (!pathHolder.el.value || pathHolder.el.value === "Non Pathway") {
            levelHolder.el.value = "";
            levelHolder.el.disabled = true;
          } else {
            levelHolder.el.disabled = false;
          }
        };
        pathHolder.el.addEventListener("change", syncLevel);

        const refreshPathwayForOwner = (ownerId) => {
          const newPath = buildPathwaySelect(ownerId);
          newPath.addEventListener("change", syncLevel);
          pathHolder.el.replaceWith(newPath);
          pathHolder.el = newPath;
        };

        // Owner picker replaces the static name header. It sits at the top of
        // the card and the pathway/level selects live below it.
        const ownerPicker = createModalOwnerPicker({
          initialOwnerId: initialOwnerId || null,
          contacts: window.allContacts && window.allContacts.length
            ? window.allContacts
            : contactsList,
          onChange: (newOwnerId, newContact) => {
            card.dataset.ownerId = newOwnerId || "";
            refreshPathwayForOwner(newOwnerId || null);
            if (newContact) {
              const defaults = getOwnerDefaults(newOwnerId);
              pathHolder.el.value = defaults.pathway;
              levelHolder.el.value = defaults.level;
            } else {
              pathHolder.el.value = "";
              levelHolder.el.value = "";
            }
            syncLevel();
          },
          placeholder: initialOwnerId ? "Change owner..." : "Add owner...",
        });

        // Mount the picker at the top of the card
        card.insertBefore(ownerPicker.wrapper, card.firstChild);

        // Initial values
        if (initialOwnerId) {
          const defaults = getOwnerDefaults(initialOwnerId);
          pathHolder.el.value = defaults.pathway;
          levelHolder.el.value = defaults.level;
        } else {
          pathHolder.el.value = "";
          levelHolder.el.value = "";
        }
        syncLevel();

        // Expose the picker on the card for save-time read
        card._ownerPicker = ownerPicker;
        card._pathHolder = pathHolder;
        card._levelHolder = levelHolder;

        return card;
      };

      // Build a card for each existing owner
      const cards = [];
      ownerIds.forEach((ownerId) => {
        const card = buildRoleOwnerCard(ownerId);
        scrollContainer.appendChild(card);
        cards.push(card);
      });

      // If no owners, show an empty card with the picker
      if (ownerIds.length === 0) {
        const card = buildRoleOwnerCard(null);
        scrollContainer.appendChild(card);
        cards.push(card);
      }

      // Add Owner button (only for roles that allow multiple owners)
      const isMultiOwnerRole = data.log.has_single_owner === false;
      if (isMultiOwnerRole) {
        const addBtn = document.createElement("button");
        addBtn.type = "button";
        addBtn.className = "btn btn-sm add-owner-btn";
        addBtn.innerHTML = '<i class="fas fa-user-plus"></i> Add Owner';
        addBtn.style.cssText = "margin-top: 10px; background: #f1f5f9; color: #475569; border: 1px dashed #cbd5e0; padding: 8px 14px; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 600;";
        addBtn.addEventListener("click", () => {
          const newCard = buildRoleOwnerCard(null);
          scrollContainer.insertBefore(newCard, addBtn);
          cards.push(newCard);
          newCard._ownerPicker.focusSearch();
        });
        scrollContainer.appendChild(addBtn);
      }

      // Stash the cards on the scroll container so save can read them
      scrollContainer._ownerCards = cards;
    } else {
      // Toggle wrappers: show speech mode, hide role mode
      modalElements.speechModeFields.style.display = "block";
      modalElements.roleModeFields.style.display = "none";
      // Restore the HTML5 required on the visible title field
      if (modalElements.speechTitle) modalElements.speechTitle.required = true;

      const setupFunctions = {
        // Project roles keyed by session_type_title
        "Evaluation": (log, opts) => SpeechModalSetupManager.setupProjectRole(log, {
          ...opts,
          projectIds: ProjectID.EVALUATION_PROJECTS,
          defaultOption: "-- Select Evaluation Project --",
          speechTitleLabelText: "Evaluator for:"
        }),
        "Individual Evaluator": (log, opts) => SpeechModalSetupManager.setupProjectRole(log, {
          ...opts,
          projectIds: ProjectID.EVALUATION_PROJECTS,
          defaultOption: "-- Select Evaluation Project --",
          speechTitleLabelText: "Evaluator for:"
        }),
        "Panel Discussion": (log, opts) => SpeechModalSetupManager.setupProjectRole(log, {
          ...opts,
          projectIds: [ProjectID.MODERATOR_PROJECT],
          defaultOption: "-- Select Panel Discussion Project --"
        }),
        "Table Topics": (log, opts) => SpeechModalSetupManager.setupProjectRole(log, {
          ...opts,
          projectIds: [ProjectID.TOPICSMASTER_PROJECT],
          defaultOption: "-- Select Table Topics Project --"
        }),
        "Keynote Speech": (log, opts) => SpeechModalSetupManager.setupProjectRole(log, {
          ...opts,
          projectIds: [ProjectID.KEYNOTE_SPEAKER_PROJECT],
          defaultOption: "-- Select Keynote Speech Project --"
        }),
        "Pathway Speech": (log, opts) => SpeechModalSetupManager.setupSpeech(log, opts),
        "Prepared Speech": (log, opts) => SpeechModalSetupManager.setupSpeech(log, opts),
        "Presentation": (log, opts) => SpeechModalSetupManager.setupSpeech(log, opts),
        // Project roles keyed by actual role.name (alias mappings)
        "Topicsmaster": (log, opts) => SpeechModalSetupManager.setupProjectRole(log, {
          ...opts,
          projectIds: [ProjectID.TOPICSMASTER_PROJECT],
          defaultOption: "-- Select Table Topics Project --"
        }),
        "Moderator": (log, opts) => SpeechModalSetupManager.setupProjectRole(log, {
          ...opts,
          projectIds: [ProjectID.MODERATOR_PROJECT],
          defaultOption: "-- Select Panel Discussion Project --"
        }),
        "Keynote Speaker": (log, opts) => SpeechModalSetupManager.setupProjectRole(log, {
          ...opts,
          projectIds: [ProjectID.KEYNOTE_SPEAKER_PROJECT],
          defaultOption: "-- Select Keynote Speech Project --"
        }),
        default: (log, opts) => SpeechModalSetupManager.setupRole(log, opts),
      };
      const setupFunction =
        setupFunctions[data.log.role] || setupFunctions[currentSessionType] || setupFunctions.default;
      setupFunction(data.log, {
        workingPath,
        nextProject,
        sessionType: currentSessionType,
      });

    }

    modalElements.modal.style.display = "flex";
  } catch (error) {
    console.error("Fetch error:", error);
    alert(`An error occurred while fetching details: ${error.message}`);
  }
}

/**
 * Closes the edit details modal.
 */
function closeEditDetailsModal() {
  modalElements.modal.style.display = "none";
}

/**
 * Main save function. Handles both role and speech updates.
 */
async function saveEditDetailsChanges(event) {
  event.preventDefault();
  const logId = modalElements.logId.value;

  const isRoleMode = modalElements.roleModeFields.style.display === "block";

  if (isRoleMode) {
    const submitBtn = modalElements.form.querySelector('button[type="submit"]');
    const originalText = submitBtn ? submitBtn.textContent : "Save";
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Saving...";
    }

    const cards = document.querySelectorAll("#role-owners-scroll .role-owner-card");
    const ownerTargets = {};
    const ownerIds = [];
    let primaryPathway = "";

    cards.forEach((card, idx) => {
      // Read the ownerId from the picker first (authoritative), fall back to
      // the legacy dataset attribute in case the picker is not present.
      const ownerId = (card._ownerPicker && card._ownerPicker.getOwnerId())
        || card.dataset.ownerId
        || "";
      const pathwayName = card._pathHolder ? card._pathHolder.el.value : (card.querySelector(".role-card-pathway")?.value || "");
      const levelVal = card._levelHolder ? card._levelHolder.el.value : (card.querySelector(".role-card-level")?.value || "");

      if (ownerId) {
        ownerIds.push(String(ownerId));
        ownerTargets[String(ownerId)] = { pathway: pathwayName, level: levelVal };
      }

      if (idx === 0) {
        primaryPathway = pathwayName;
      }
    });

    try {
      const response = await fetch(`/speech_log/update/${logId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ owner_ids: ownerIds, owner_targets: ownerTargets })
      });
      const data = await response.json();
      if (data.success) {
        const row = document.querySelector(`tr[data-id="${logId}"]`);
        if (row) {
          row.dataset.ownerTargets = JSON.stringify(ownerTargets);
          row.dataset.ownerIds = JSON.stringify(ownerIds);
          row.dataset.ownerId = ownerIds[0] || "";
          row.dataset.pathway = primaryPathway;
        }

        const affectedLogIds = [logId];
        if (data.affected_log_ids && data.affected_log_ids.length > 0) {
          affectedLogIds.push(...data.affected_log_ids);
        }

        affectedLogIds.forEach(id => {
          const affectedRow = document.querySelector(`tr[data-id="${id}"]`);
          if (affectedRow) {
            affectedRow.dataset.ownerTargets = JSON.stringify(ownerTargets);
            affectedRow.dataset.pathway = primaryPathway;
          }
        });

        if (!window.location.pathname.includes("/agenda")) {
          window.location.reload();
        } else {
          // Owner names need a full re-render. Reload the agenda so the new
          // owner's name + credentials appear in the row.
          const priorOwnerIds = (() => {
            if (!row) return null;
            try { return JSON.parse(row.dataset.ownerIds || "[]"); } catch (_) { return null; }
          })();
          const ownerChanged =
            !priorOwnerIds ||
            priorOwnerIds.length !== ownerIds.length ||
            priorOwnerIds.some((id, i) => String(id) !== String(ownerIds[i]));
          if (ownerChanged) {
            window.location.reload();
          } else {
            closeEditDetailsModal();
          }
        }
      } else {
        alert("Error saving: " + (data.message || "Unknown error"));
      }
    } catch (error) {
      console.error("Save error:", error);
      alert("An error occurred while saving: " + error.message);
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
      }
    }
  } else {
    // Speech/Project mode save
    const payload = buildSavePayload();

    try {
      const response = await fetch(`/speech_log/update/${logId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const updateResult = await response.json();
      if (updateResult.success) {
        handleSaveSuccess(updateResult, payload);
      } else {
        throw new Error(updateResult.message || "Unknown error");
      }
    } catch (error) {
      console.error("Save error:", error);
      alert(`An error occurred while saving changes: ${error.message}`);
    }
  }
}

// Expose functions globally
window.openEditDetailsModal = openEditDetailsModal;
window.closeEditDetailsModal = closeEditDetailsModal;
window.saveEditDetailsChanges = saveEditDetailsChanges;


// --- Setup Helpers ---

/**
 * Mount a single-owner picker into a speech-mode card. Replaces the static
 * owner name element. When the owner changes, the pathway dropdown is
 * repopulated for the new owner and the level dropdown is reset.
 *
 * The returned picker is also stashed on modalElements.ownerPicker so the
 * save logic can read it.
 */
function mountSpeechModeOwnerPicker({
  ownerNameElement,
  pathwaySelectEl,
  levelSelectEl,
  logData,
  workingPath,
  repopulatePathway,
}) {
  if (!ownerNameElement) return null;

  // Remove any prior picker that may have been mounted on a previous open
  const existingWrapper = ownerNameElement.parentNode?.querySelector(".modal-owner-picker");
  if (existingWrapper) existingWrapper.remove();

  const picker = createModalOwnerPicker({
    initialOwnerId: logData.owner_id || null,
    contacts: (window.allContacts && window.allContacts.length)
      ? window.allContacts
      : (logData.owners_data || []),
    onChange: (newOwnerId, newContact) => {
      const registeredPaths = (newContact && newContact.registered_paths)
        ? newContact.registered_paths.map((p) => typeof p === 'object' ? p.name : p)
        : null;
      repopulatePathway(newOwnerId, registeredPaths);

      // Recompute default pathway & level for the new owner
      let defaultPath = "Non Pathway";
      if (newContact) {
        if (newContact.Type === "Guest" || !newContact.Current_Path) {
          defaultPath = "Non Pathway";
        } else {
          defaultPath = newContact.Current_Path;
        }
      }
      // Preserve a saved target for the new owner if present
      const savedTarget = logData.owner_targets && logData.owner_targets[String(newOwnerId)];
      if (savedTarget && savedTarget.pathway) {
        defaultPath = savedTarget.pathway;
      }
      pathwaySelectEl.value = defaultPath;

      if (defaultPath === "Non Pathway") {
        if (levelSelectEl) {
          levelSelectEl.value = "";
          levelSelectEl.disabled = true;
        }
      } else if (levelSelectEl) {
        const levelMatch = (newContact && newContact.Credentials || "").match(/\d+/);
        const defaultLevel = savedTarget && savedTarget.level
          ? savedTarget.level
          : (levelMatch ? Math.min(parseInt(levelMatch[0], 10) + 1, 5).toString() : "1");
        levelSelectEl.value = defaultLevel;
        levelSelectEl.disabled = false;
      }
    },
    placeholder: logData.owner_id ? "Change owner..." : "Add owner...",
  });

  ownerNameElement.replaceWith(picker.wrapper);
  modalElements.ownerPicker = picker;
  return picker;
}

function resetModal(logData, sessionType) {
  toggleGeneric(false);
  modalElements.form.reset();
  modalElements.logId.value = logData.id;
  modalElements.title.textContent = "Edit Details";
  modalElements.sessionOwner.value = logData.owner_name || "";
  modalElements.speechTitle.value = logData.Session_Title || "";
  modalElements.credential.value = logData.credential || "";
  modalElements.sessionType.value = sessionType;
  modalElements.mediaUrl.value = logData.Media_URL || "";
  modalElements.speechTitle.disabled = false;
  modalElements.credential.disabled = false;
  
  // Reset visibility of Speech Title form group (might be hidden by role modal)
  const speechTitleRow = modalElements.speechTitle.closest('.form-group, .sem-field');
  if (speechTitleRow) speechTitleRow.style.display = 'block';

  // Reset disabled states for checkboxes and clear custom event handlers
  if (modalElements.isProjectCheckbox) {
    modalElements.isProjectCheckbox.disabled = false;
  }
  if (modalElements.isProjectChk) {
    modalElements.isProjectChk.disabled = false;
    modalElements.isProjectChk.onchange = null;
  }
  if (modalElements.pathwaySelectDropdown) {
    modalElements.pathwaySelectDropdown.onchange = null;
  }
  if (modalElements.levelSelectDropdown) {
    modalElements.levelSelectDropdown.disabled = false;
  }
  if (modalElements.levelSelect) {
    modalElements.levelSelect.disabled = false;
  }

  if (modalElements.standardSelection)
    modalElements.standardSelection.style.display = "none";

  const optionalElements = [
    modalElements.pathwayGenericRow,
    modalElements.levelSelectGroup,
    modalElements.projectSelectGroup,
    modalElements.projectGroup,
    modalElements.pathwayGroup,
    modalElements.projectModeFields,
    modalElements.standardProjectFields,
  ];
  optionalElements.forEach((el) => {
    if (el) el.style.display = "none";
  });

  modalElements.speechTitleLabel.textContent = "Session Title:";
  modalElements.labelPathway.textContent = "Pathway:";
  modalElements.labelLevel.textContent = "Level:";
  modalElements.labelProject.textContent = "Project:";
  modalElements.pathwaySelect.required = false;
}

const SpeechModalSetupManager = {
  populatePathwayDropdown(dropdown, ownerId, logRegisteredPaths, ownersData = null) {
    const contactsList = ownersData || window.allContacts || [];
    const contact = contactsList.find((c) => c.id == ownerId);
    let regPaths = [];
    if (contact && contact.registered_paths) {
      regPaths = contact.registered_paths.map(p => typeof p === 'object' ? p.name : p);
    } else if (logRegisteredPaths) {
      regPaths = logRegisteredPaths.map(p => typeof p === 'object' ? p.name : p);
    }

    dropdown.innerHTML = '';
    if (regPaths.length > 0) {
      dropdown.add(new Option("-- Select Pathway --", ""));
      regPaths.forEach((name) => {
        dropdown.add(new Option(name, name));
      });
      if (!regPaths.includes("Non Pathway")) {
        dropdown.add(new Option("Non Pathway", "Non Pathway"));
      }
    } else {
      dropdown.add(new Option("Non Pathway", "Non Pathway"));
    }
  },

  setupRole(logData, { sessionType, workingPath }) {
    modalElements.title.textContent = "Edit Details";
    modalElements.speechTitle.disabled = true;
    modalElements.standardSelection.style.display = "none";
    modalElements.projectGroup.style.display = "none";
    const speechTitleRow = modalElements.speechTitle.closest('.form-group, .sem-field');
    if (speechTitleRow) speechTitleRow.style.display = 'none';

    // Mount owner picker in place of the static owner name
    mountSpeechModeOwnerPicker({
      ownerNameElement: document.getElementById("project-role-owner-name"),
      pathwaySelectEl: modalElements.pathwaySelectDropdown,
      levelSelectEl: modalElements.levelSelectDropdown,
      logData,
      workingPath,
      repopulatePathway: (newOwnerId, registeredPaths) => {
        SpeechModalSetupManager.populatePathwayDropdown(
          modalElements.pathwaySelectDropdown,
          newOwnerId,
          registeredPaths,
          logData.owners_data
        );
      },
    });

    // Show pathway dropdown for all roles (unified pathway handling)
    modalElements.pathwayGroup.style.display = "flex";
    if (modalElements.levelGroup) {
      modalElements.levelGroup.style.display = "block";
    }
    SpeechModalSetupManager.populatePathwayDropdown(modalElements.pathwaySelectDropdown, logData.owner_id, logData.registered_paths, logData.owners_data);
    // Priority: target_pathway (from OwnerMeetingRoles) > owner's Current_Path or workingPath > "Non Pathway"
    let defaultPath = logData.target_pathway;
    if (defaultPath === undefined || defaultPath === null || defaultPath === "") {
      const contactsList = logData.owners_data || window.allContacts || [];
      const contact = contactsList.find((c) => c.id == logData.owner_id);
      defaultPath = (contact && contact.Current_Path) || workingPath || "Non Pathway";
    }
    modalElements.pathwaySelectDropdown.value = defaultPath;
    
    // Priority: target_level (from OwnerMeetingRoles) > empty
    let defaultLevel = logData.target_level;
    if (defaultLevel === undefined || defaultLevel === null || defaultLevel === "") {
      defaultLevel = "";
    }
    modalElements.levelSelectDropdown.value = defaultLevel;

    const syncRoleLevel = () => {
      const pathway = modalElements.pathwaySelectDropdown.value;
      if (pathway === "Non Pathway") {
        if (modalElements.levelSelectDropdown) {
          modalElements.levelSelectDropdown.value = "";
          modalElements.levelSelectDropdown.disabled = true;
        }
      } else {
        if (modalElements.levelSelectDropdown) {
          modalElements.levelSelectDropdown.disabled = false;
        }
      }
    };
    modalElements.pathwaySelectDropdown.onchange = () => {
      syncRoleLevel();
    };
    syncRoleLevel();
  },

  getTitlePlaceholder(sessionType) {
    const placeholders = {
      "Keynote Speech": "e.g. The Leader in You",
      "Keynote Speaker": "e.g. The Leader in You",
      "Table Topics": "e.g. Table Topics",
      "Topicsmaster": "e.g. Table Topics",
      "Panel Discussion": "e.g. Panel Discussion",
      "Moderator": "e.g. Panel Discussion",
      "Evaluation": "e.g. Evaluating Tom's Ice Breaker",
      "Individual Evaluator": "e.g. Evaluating Tom's Ice Breaker",
      "Prepared Speech": "e.g. My Ice Breaker",
      "Pathway Speech": "e.g. My Pathway Speech",
      "Presentation": "e.g. My Club Presentation",
    };
    return placeholders[sessionType] || "Enter title";
  },

  setupProjectRole(logData, { sessionType, workingPath, projectIds, defaultOption, speechTitleLabelText }) {
    modalElements.title.textContent = "Edit Details";
    if (speechTitleLabelText) {
      modalElements.speechTitleLabel.textContent = speechTitleLabelText;
    }
    // Evaluation / Individual Evaluator: title holds the speaker being evaluated
    // (used by backend's speaker_is_dtm lookup) — keep it locked to that name.
    const editableTitleTypes = [
      "Keynote Speech", "Keynote Speaker",
      "Table Topics", "Topicsmaster",
      "Panel Discussion", "Moderator",
    ];
    modalElements.speechTitle.disabled = !editableTitleTypes.includes(sessionType);
    modalElements.speechTitle.placeholder = SpeechModalSetupManager.getTitlePlaceholder(sessionType);

    // Mount owner picker in place of the static owner name
    mountSpeechModeOwnerPicker({
      ownerNameElement: document.getElementById("project-role-owner-name"),
      pathwaySelectEl: modalElements.pathwaySelectDropdown,
      levelSelectEl: modalElements.levelSelectDropdown,
      logData,
      workingPath,
      repopulatePathway: (newOwnerId, registeredPaths) => {
        SpeechModalSetupManager.populatePathwayDropdown(
          modalElements.pathwaySelectDropdown,
          newOwnerId,
          registeredPaths,
          logData.owners_data
        );
      },
    });

    modalElements.projectGroup.style.display = "block";
    modalElements.pathwayGroup.style.display = "flex";
    if (modalElements.levelGroup) {
      modalElements.levelGroup.style.display = "block";
    }

    const targetProjectIds = Array.isArray(projectIds)
      ? projectIds.map(Number)
      : [Number(projectIds)];

    const projectsList = allProjects
      .filter((p) => targetProjectIds.includes(Number(p.id)))
      .sort((a, b) => a.id - b.id);

    populateDropdown(modalElements.projectSelectDropdown, projectsList, {
      defaultOption: defaultOption,
      valueField: "id",
      textField: "Project_Name"
    });

    if (projectsList.length === 1) {
      modalElements.projectSelectDropdown.value = projectsList[0].id;
    }

    this.populatePathwayDropdown(modalElements.pathwaySelectDropdown, logData.owner_id, logData.registered_paths, logData.owners_data);

    // Priority: target_pathway (from OwnerMeetingRoles) > owner's Current_Path or workingPath > "Non Pathway"
    let defaultPath = logData.target_pathway;
    if (defaultPath === undefined || defaultPath === null || defaultPath === "") {
      const contactsList = logData.owners_data || window.allContacts || [];
      const contact = contactsList.find((c) => c.id == logData.owner_id);
      defaultPath = (contact && contact.Current_Path) || workingPath || "Non Pathway";
    }
    modalElements.pathwaySelectDropdown.value = defaultPath;
    
    let defaultLevel = logData.target_level;
    if (defaultLevel === undefined || defaultLevel === null || defaultLevel === "") {
      defaultLevel = "";
    }
    if (modalElements.levelSelectDropdown) {
        modalElements.levelSelectDropdown.value = defaultLevel;
    }

    const isProject = logData.Project_ID && targetProjectIds.includes(Number(logData.Project_ID));

    const toggleFields = (isChecked) => {
      modalElements.projectModeFields.style.display = isChecked ? "block" : "none";
      if (modalElements.projectSelectDropdown && sessionType !== "Evaluation" && sessionType !== "Individual Evaluator") {
        modalElements.projectSelectDropdown.style.display = isChecked ? "block" : "none";
      }
      if (!isChecked) {
        modalElements.projectSelectDropdown.value = "";
        if (sessionType === "Evaluation" || sessionType === "Individual Evaluator") {
          modalElements.speechTitle.value = logData.Session_Title || "";
        }
      } else {
        if (projectsList.length === 1) {
          modalElements.projectSelectDropdown.value = projectsList[0].id;
        } else if (isProject) {
          modalElements.projectSelectDropdown.value = logData.Project_ID;
        }
      }
    };

    const syncProjectChk = () => {
      const pathway = modalElements.pathwaySelectDropdown.value;
      if (pathway === "Non Pathway") {
        modalElements.isProjectChk.checked = false;
        modalElements.isProjectChk.disabled = true;
        if (modalElements.levelSelectDropdown) {
          modalElements.levelSelectDropdown.value = "";
          modalElements.levelSelectDropdown.disabled = true;
        }
        toggleFields(false);
      } else {
        modalElements.isProjectChk.disabled = false;
        if (modalElements.levelSelectDropdown) {
          modalElements.levelSelectDropdown.disabled = false;
        }
      }
    };

    modalElements.pathwaySelectDropdown.onchange = () => {
      syncProjectChk();
    };

    modalElements.isProjectChk.onchange = (e) => toggleFields(e.target.checked);
    
    // Initial sync and toggle setup
    syncProjectChk();
    if (modalElements.pathwaySelectDropdown.value !== "Non Pathway") {
      modalElements.isProjectChk.checked = isProject;
      toggleFields(isProject);
    }
  },

  setupSpeech(logData, { workingPath, nextProject, sessionType }) {
    modalElements.title.textContent = "Edit Details";
    modalElements.speechTitle.placeholder = SpeechModalSetupManager.getTitlePlaceholder(sessionType);
    modalElements.standardSelection.style.display = "block";
    if (modalElements.standardProjectFields) {
      modalElements.standardProjectFields.style.display = "block";
    }
    modalElements.pathwaySelect.required = true;
    modalElements.pathwayGenericRow.style.display = "block";
    modalElements.levelSelectGroup.style.display = "block";
    modalElements.projectSelectGroup.style.display = "block";

    // Mount owner picker in place of the static owner name
    mountSpeechModeOwnerPicker({
      ownerNameElement: document.getElementById("speech-owner-name"),
      pathwaySelectEl: modalElements.pathwaySelect,
      levelSelectEl: modalElements.levelSelect,
      logData,
      workingPath,
      repopulatePathway: (newOwnerId, registeredPaths) => {
        SpeechModalSetupManager.populatePathwayDropdown(
          modalElements.pathwaySelect,
          newOwnerId,
          registeredPaths,
          logData.owners_data
        );
      },
    });

    modalElements.labelPathway.textContent = "Pathway:";
    modalElements.labelProject.textContent = "Project:";
    modalElements.labelLevel.textContent = "Level:";

    this.populatePathwayDropdown(modalElements.pathwaySelect, logData.owner_id, logData.registered_paths, logData.owners_data);

    let pathwayToSelect = logData.target_pathway;
    let levelToSelect = logData.target_level;
    let projectToSelect = logData.Project_ID;
    const projectCode = logData.project_code || nextProject;

    // REQUIREMENT: Populate path/level/project based on project_code if available and non-generic
    if (projectCode && !['TM1.0', '', 'null'].includes(projectCode)) {
      const codeMatch = projectCode.match(/^([A-Z]+)(\d+(?:\.\d+)?)$/);
      if (codeMatch) {
        const abbr = codeMatch[1];
        const codePart = codeMatch[2];

        const pathwayName = Object.keys(pathwayMap).find(name => pathwayMap[name] === abbr);
        if (pathwayName) {
          pathwayToSelect = pathwayName;
          
          if (projectToSelect && projectToSelect != ProjectID.GENERIC) {
            // Already have a specific project ID, look up its level for this pathway
            const foundProject = allProjects.find(p => Number(p.id) === Number(projectToSelect));
            if (foundProject && foundProject.path_codes[abbr]) {
              levelToSelect = foundProject.path_codes[abbr].level;
            }
          } else {
            // Find first matching project by pathway and code part
            const foundProject = allProjects.find(p => p.path_codes[abbr] && String(p.path_codes[abbr].code) === codePart);
            if (foundProject) {
              projectToSelect = foundProject.id;
              levelToSelect = foundProject.path_codes[abbr].level;
            }
          }
        }
      }
    }

    if (!pathwayToSelect) {
      const contactsList = logData.owners_data || window.allContacts || [];
      const contact = contactsList.find((c) => c.id == logData.owner_id);
      pathwayToSelect = (contact && contact.Current_Path) || workingPath || "";
    }

    // Fallback: derive level if pathway and project are set but level is not
    if (pathwayToSelect && pathwayToSelect !== "Non Pathway" && projectToSelect && projectToSelect != ProjectID.GENERIC && !levelToSelect) {
      const abbr = pathwayMap[pathwayToSelect];
      if (abbr) {
        const foundProject = allProjects.find(p => Number(p.id) === Number(projectToSelect));
        if (foundProject && foundProject.path_codes[abbr]) {
          levelToSelect = foundProject.path_codes[abbr].level;
        }
      }
    }

    if (!pathwayToSelect) {
      pathwayToSelect = "Non Pathway";
    }

    // Ensure level value is string type to match dropdown options
    if (levelToSelect !== undefined && levelToSelect !== null) {
      levelToSelect = String(levelToSelect);
    }

    const isGeneric = projectToSelect == ProjectID.GENERIC;

    modalElements.pathwaySelect.value = pathwayToSelect || "";

    if (pathwayToSelect === "Non Pathway") {
      modalElements.isProjectCheckbox.checked = false;
      modalElements.isProjectCheckbox.disabled = true;
      toggleGeneric(true);
      if (modalElements.levelSelect) {
        modalElements.levelSelect.value = "";
        modalElements.levelSelect.disabled = true;
      }
    } else {
      modalElements.isProjectCheckbox.disabled = false;
      modalElements.isProjectCheckbox.checked = !isGeneric;
      toggleGeneric(isGeneric);
      if (!isGeneric) {
        updateLevelOptions();
        modalElements.levelSelect.value = levelToSelect || "";
        updateProjectOptions(projectToSelect);
      }
    }
  }
};

// --- Dynamic Dropdown Helpers ---

function updateDynamicOptions() {
  const pathway = modalElements.pathwaySelect.value;
  if (pathway === "Non Pathway") {
    modalElements.isProjectCheckbox.checked = false;
    modalElements.isProjectCheckbox.disabled = true;
    toggleGeneric(true);
    if (modalElements.levelSelect) {
      modalElements.levelSelect.value = "";
      modalElements.levelSelect.disabled = true;
    }
  } else {
    modalElements.isProjectCheckbox.disabled = false;
    updateLevelOptions();
    updateProjectOptions();
  }
}

function updateLevelOptions() {
  const { pathwaySelect, levelSelect } = modalElements;
  const pathwayName = pathwaySelect.value;
  const currentLevel = levelSelect.value;

  if (!pathwayName) return;

  const codeSuffix = (typeof pathwayMap !== 'undefined' ? pathwayMap[pathwayName] : null);

  if (!codeSuffix) return;

  // Find all unique levels for this pathway
  const availableLevels = new Set();

  allProjects.forEach(p => {
    const info = p.path_codes[codeSuffix];
    if (info && (info.level || info.level === 0 || info.level === '0')) {
      availableLevels.add(info.level);
    }
  });

  // Sort levels
  const sortedLevels = Array.from(availableLevels).sort((a, b) => a - b);

  // Rebuild Level Options
  // Keep "All Levels" or empty option if that's desired? 
  // Usually for editing a speech, we want to force valid selection.
  // But let's keep a default prompt.
  levelSelect.innerHTML = '<option value="">-- Select Level --</option>';

  sortedLevels.forEach(lvl => {
    levelSelect.add(new Option(`Level ${lvl}`, lvl));
  });

  // Restore selection if valid, otherwise clear
  if (availableLevels.has(parseInt(currentLevel))) {
    levelSelect.value = currentLevel;
  } else if (availableLevels.has(currentLevel)) { // Check string match
    levelSelect.value = currentLevel;
  } else {
    levelSelect.value = "";
  }
}

function updateProjectOptions(selectedProjectId = null) {
  const { pathwaySelect, levelSelect, projectSelect } = modalElements;
  const pathwayName = pathwaySelect.value;
  const level = levelSelect.value;
  // If we know it's a presentation (e.g. from session type context, or checking value), behavior is same
  // except maybe validation. But `pathwayMap` handles translation of name to 'code'.
  // For presentations, we might need to handle series names if they aren't in pathwayMap or handle them generically.
  // Actually, 'pathwayMap' is critical here. It maps "Presentation Mastery" -> "PM".
  // For series like "Successful Club Series", do we have a mapping?
  // If not, we need a way to look it up or rely on logic that presentation series are treated as pathways.
  // Backend passes "Successful Club Series" as pathway name. 
  // We need to ensure `pathwayMap` or similar logical structure supports it.

  // Assuming the `groupedPathways` or `pathwayMap` on page load contains Series now?
  // The backend `pathway_library` route includes series if they are in `Pathway` table.

  // Let's assume standard logic works if `pathwayMap` or equivalent is updated or valid.
  // If `codeSuffix` is undefined, we might fail to find keys.

  const codeSuffix = (typeof pathwayMap !== 'undefined' ? pathwayMap[pathwayName] : null);

  /* console.log("Debug updateProjectOptions:", { pathwayName, codeSuffix, level }); */

  projectSelect.innerHTML = '<option value="">-- Select a Project --</option>';
  if (!codeSuffix) {
    // console.warn("No code suffix found for pathway:", pathwayName);
    return;
  }

  const filteredProjects = allProjects
    .filter(p => {
      // Backend now sends path_codes as objects: { code: '...', level: 5 }
      const pathInfo = p.path_codes[codeSuffix];
      if (!pathInfo) return false;

      const { code, level: projectLevel } = pathInfo;

      if (level) {
        // Strict, explicit level check from DB (as requested)
        // Ensure string comparison to handle any type mismatches
        return String(projectLevel) === String(level);
      }
      return true;
    })
    .sort((a, b) => {
      const infoA = a.path_codes[codeSuffix];
      const infoB = b.path_codes[codeSuffix];

      // Sort by Level first
      if (infoA.level !== infoB.level) {
        return infoA.level - infoB.level;
      }

      // Then Numeric Code if possible
      const fA = parseFloat(infoA.code);
      const fB = parseFloat(infoB.code);
      if (!isNaN(fA) && !isNaN(fB)) {
        return fA - fB;
      }
      // Fallback to string sort
      return infoA.code.localeCompare(infoB.code);
    });

  filteredProjects.forEach((p) => {
    const info = p.path_codes[codeSuffix];
    // Display: "Code - Name"
    projectSelect.add(new Option(`${info.code} - ${p.Project_Name}`, p.id));
  });

  if (selectedProjectId) projectSelect.value = selectedProjectId;
}

// --- Save Helpers ---

function buildSavePayload() {
  const {
    sessionType,
    mediaUrl,
    credential,
    isProjectChk,
    speechTitle,
    projectSelect,
    pathwaySelect,
    projectSelectDropdown,
    pathwaySelectDropdown,
  } = modalElements;
  const payload = {
    session_type_title: sessionType.value,
    media_url: mediaUrl.value || null,
    credential: credential.value || null,
    session_title: speechTitle.value || "",
  };
  const isProject = isProjectChk?.checked || false;

  // If the speech-mode owner picker is mounted, send the chosen owner so
  // the backend persists the change. (Owner is single per speech-mode log.)
  if (modalElements.ownerPicker) {
    const newOwnerId = modalElements.ownerPicker.getOwnerId();
    if (newOwnerId) {
      payload.owner_id = newOwnerId;
    }
  }

  // Helper to read the level dropdown (shared across all session types that use pathwayGroup)
  const levelDropdownValue = modalElements.levelSelectDropdown
    ? modalElements.levelSelectDropdown.value || null
    : null;

  switch (sessionType.value) {
    case "Panel Discussion":
    case "Moderator":
      payload.project_id = isProject ? ProjectID.MODERATOR_PROJECT : null;
      payload.pathway = pathwaySelectDropdown.value || "";
      payload.level = levelDropdownValue;
      break;
    case "Table Topics":
    case "Topicsmaster":
      payload.project_id = isProject ? ProjectID.TOPICSMASTER_PROJECT : null;
      payload.pathway = pathwaySelectDropdown.value || "";
      payload.level = levelDropdownValue;
      break;
    case "Keynote Speech":
    case "Keynote Speaker":
      payload.project_id = isProject ? ProjectID.KEYNOTE_SPEAKER_PROJECT : null;
      payload.pathway = pathwaySelectDropdown.value || "";
      payload.level = levelDropdownValue;
      break;
    case "Evaluation":
    case "Individual Evaluator":
      payload.project_id =
        isProject && projectSelectDropdown.value
          ? projectSelectDropdown.value
          : null;
      payload.pathway = pathwaySelectDropdown.value || "";
      payload.level = levelDropdownValue;
      break;
    default:
      // Include speech-specific fields if the standard selection UI is visible
      if (modalElements.standardSelection && modalElements.standardSelection.style.display !== "none") {
        const isGeneric = !modalElements.isProjectCheckbox.checked;
        payload.project_id = isGeneric ? ProjectID.GENERIC : projectSelect.value || ProjectID.GENERIC;
        payload.pathway = pathwaySelect.value;
        payload.level = modalElements.levelSelect.value || null;
      } else {
        // For roles (GE, Timer, etc.), send the pathway and level from the pathway-group dropdowns
        payload.pathway = pathwaySelectDropdown.value || "";
        payload.level = levelDropdownValue;
      }
      break;
  }
  return payload;
}

function handleSaveSuccess(updateResult, payload) {
  const logId = modalElements.logId.value;

  if (!window.location.pathname.includes("/agenda")) {
    window.location.reload();
    return;
  }

  const logsToUpdate = [logId];
  if (updateResult.affected_log_ids && updateResult.affected_log_ids.length > 0) {
    logsToUpdate.push(...updateResult.affected_log_ids);
  }

  logsToUpdate.forEach(id => {
    updateAgendaRow(id, updateResult, payload);
  });

  // Refresh the main log's owner cell with the new per-owner credentials
  // returned by the server, so the agenda reflects the change without a
  // full page reload. Owners of *affected* logs are unchanged.
  if (Array.isArray(updateResult.owners_data) && updateResult.owners_data.length > 0) {
    const mainRow = document.querySelector(`tr[data-id="${logId}"]`);
    if (mainRow) {
      refreshAgendaOwnerCell(mainRow, updateResult.owners_data);
    }
  }

  closeEditDetailsModal();
}

// Update the owner column of an agenda row so each owner's displayed
// credential matches the freshly-saved value. Mirrors the static template
// in agenda.html: DTM is rendered as <sup class="dtm-superscript">,
// everything else as <span class="owner-meta"> - CRED</span>. Award
// badges and owner-name links are left untouched.
function refreshAgendaOwnerCell(agendaRow, ownersData) {
  if (!agendaRow || !Array.isArray(ownersData) || ownersData.length === 0) return;

  const ownerCell = agendaRow.querySelector("td.col-owner");
  if (!ownerCell) return;

  const ownerRows = ownerCell.querySelectorAll(".owner-row");
  // Match by position: the server response and the rendered cell both
  // list owners in the same order (log.owners).
  ownersData.forEach((owner, idx) => {
    const ownerRow = ownerRows[idx];
    if (!ownerRow) return;

    const existingSup = ownerRow.querySelector(".dtm-superscript");
    if (existingSup) existingSup.remove();
    const existingMeta = ownerRow.querySelector(".owner-meta");
    if (existingMeta) existingMeta.remove();

    if (owner.credentials === "DTM") {
      const sup = document.createElement("sup");
      sup.className = "dtm-superscript";
      sup.textContent = "DTM";
      ownerRow.appendChild(sup);
    } else if (owner.credentials) {
      const meta = document.createElement("span");
      meta.className = "owner-meta";
      meta.textContent = ` - ${owner.credentials}`;
      ownerRow.appendChild(meta);
    }
  });

  // Keep the row-level data-credentials in sync with the primary owner
  // so the next save round-trips the new value and the dataset reflects
  // what is on screen.
  if (ownersData[0]) {
    agendaRow.dataset.credentials = ownersData[0].credentials || "";
  }
}

// --- UI Update Functions ---

function updateAgendaRow(logId, updateResult, payload) {
  const agendaRow = document.querySelector(`tr[data-id="${logId}"]`);
  if (!agendaRow) return;

  const { session_type_title: sessionType, media_url: newMediaUrl } = payload;

  const updateMediaLink = (cell) => {
    let mediaLink = cell.querySelector(".media-play-btn");
    const wrapper = cell.querySelector(".speech-tooltip-wrapper") || cell;
    if (newMediaUrl) {
      if (!mediaLink) {
        mediaLink = document.createElement("a");
        mediaLink.target = "_blank";
        mediaLink.className = "icon-btn media-play-btn";
        mediaLink.title = "Watch Media";
        mediaLink.innerHTML = ' <i class="fas fa-play-circle"></i>';
        wrapper.appendChild(mediaLink);
      }
      mediaLink.href = newMediaUrl;
    } else if (mediaLink) {
      mediaLink.remove();
    }
  };

  // Always sync pathway on the row dataset (unified for all role types)
  if (updateResult.pathway !== undefined) {
    agendaRow.dataset.pathway = updateResult.pathway || "";
  }

  // Always update the edit-mode title cell (if the row is in edit mode)
  // so the user's typed value is reflected in the agenda immediately.
  const editTitleCell = agendaRow.querySelector(
    'td[data-field="Session_Title"]'
  );
  if (editTitleCell) {
    const ctl = editTitleCell.querySelector("input, select, span");
    if (ctl)
      ctl.tagName === "SPAN"
        ? (ctl.textContent = updateResult.session_title)
        : (ctl.value = updateResult.session_title);
  }

  if (sessionType === "Table Topics" || sessionType === "Panel Discussion" || sessionType === "Keynote Speech") {
    agendaRow.dataset.projectId = updateResult.project_id || "";
    agendaRow.dataset.sessionTitle = updateResult.session_title || "";
    const viewTitleCell = agendaRow.querySelector(
      ".non-edit-mode-cell:nth-child(2)"
    );
    if (viewTitleCell) {
      // Server is the source of truth: the saved session_title is the title to show.
      // If the server didn't persist a title (e.g. cleared + no project), fall back
      // to the role display name the server also returns, so the cell is never blank.
      const title = updateResult.session_title || updateResult.role_display_name || sessionType;
      const code = updateResult.project_code ? `(${updateResult.project_code})` : "";

      const projName = updateResult.project_name;
      const proj = allProjects.find((p) => p.id == updateResult.project_id);
      const projPurpose = proj ? proj.Purpose : "";

      viewTitleCell.innerHTML = ""; // Clear
      const wrapper = document.createElement("div");
      wrapper.className = "speech-tooltip-wrapper";
      wrapper.textContent = `${title} ${code}`.trim();

      if (updateResult.project_id && updateResult.project_id != ProjectID.GENERIC) {
        const tooltip = document.createElement("div");
        tooltip.className = "speech-tooltip";
        tooltip.innerHTML = `<span class="tooltip-title">${projName || ""
          }</span><span class="tooltip-purpose">${projPurpose || ""}</span>`;
        wrapper.appendChild(tooltip);
      }
      viewTitleCell.appendChild(wrapper);
      updateMediaLink(viewTitleCell);
    }
    return;
  }

  agendaRow.dataset.projectId = updateResult.project_id || "";
  agendaRow.dataset.sessionTitle = updateResult.session_title;
  agendaRow.dataset.durationMin = updateResult.duration_min || "";
  agendaRow.dataset.durationMax = updateResult.duration_max || "";
  agendaRow.dataset.pathway = updateResult.pathway || "";

  // Update Duration Inputs (Fixes overwrite issue)
  const durationMinInput = agendaRow.querySelector(
    '[data-field="Duration_Min"] input'
  );
  if (durationMinInput) {
    durationMinInput.value = updateResult.duration_min || "";
  }

  const durationMaxInput = agendaRow.querySelector(
    '[data-field="Duration_Max"] input'
  );
  if (durationMaxInput) {
    durationMaxInput.value = updateResult.duration_max || "";
  }

  // Update View Mode Title
  const viewTitleCell = agendaRow.querySelector(
    ".non-edit-mode-cell:nth-child(2)"
  );
  if (viewTitleCell) {
    let title = updateResult.session_title;
    if (sessionType === "Evaluation" || sessionType === "Individual Evaluator") {
      let cleaned = title ? title.replace(/"/g, "") : "";
      title = "Evaluator for " + cleaned;
    } else if ((sessionType === "Pathway Speech" || sessionType === "Prepared Speech" || sessionType === "Presentation") && updateResult.project_id != ProjectID.GENERIC) {
      title = `"${title.replace(/"/g, "")}"`;
    }
    let code = updateResult.project_code
      ? `(${updateResult.project_code})`
      : "";
    if (updateResult.project_id == ProjectID.GENERIC) code = "(TM1.0)";

    let projName = updateResult.project_name;
    let projPurpose = "";
    const proj = allProjects.find((p) => p.id == updateResult.project_id);
    if (proj) {
      projName = proj.Project_Name;
      projPurpose = proj.Purpose;
    }

    viewTitleCell.innerHTML = "";
    const wrapper = document.createElement("div");
    wrapper.className = "speech-tooltip-wrapper";

    // Title text node (no link wrapping needed; the project code gets its own
    // clickable <a> below).
    wrapper.appendChild(document.createTextNode(title));

    if ((sessionType === "Evaluation" || sessionType === "Individual Evaluator") && updateResult.speaker_is_dtm) {
      const sup = document.createElement("sup");
      sup.className = "dtm-superscript";
      sup.textContent = "DTM";
      wrapper.appendChild(sup);
    }

    // Project code as a clickable <a> with the project-code-link class.
    // This matches the server-rendered template and the post-update render
    // path in agenda.js — so the badge is consistent everywhere a row
    // gets re-rendered. Plain text here would look like a badge but
    // do nothing on click.
    if (code) {
      wrapper.appendChild(document.createTextNode(' '));
      const aCode = document.createElement('a');
      aCode.className = 'project-code-link';
      aCode.textContent = code;
      // Build the best href we can. If pathway/level are derivable from
      // the response, link to the specific project; otherwise fall back
      // to the library index.
      const pathwayCode = updateResult.pathway_code;
      const level = updateResult.level;
      if (updateResult.project_id && pathwayCode && level != null) {
        aCode.href = `/pathway_library?path=${pathwayCode}&level=${level}&project_id=${updateResult.project_id}`;
        aCode.title = 'View in Pathways Library';
      } else {
        aCode.href = '/pathway_library';
        aCode.title = 'Open Pathways Library';
      }
      wrapper.appendChild(aCode);
    }

    if (updateResult.project_id && updateResult.project_id != ProjectID.GENERIC) {
      const tooltip = document.createElement("div");
      tooltip.className = "speech-tooltip";
      tooltip.innerHTML = `<span class="tooltip-title">${projName || ""
        }</span><span class="tooltip-purpose">${projPurpose || ""}</span>`;
      wrapper.appendChild(tooltip);
    }
    viewTitleCell.appendChild(wrapper);
    updateMediaLink(viewTitleCell);
  }

  // Update View Mode Duration Cell
  const durationCell = agendaRow.querySelector(
    ".non-edit-mode-cell:nth-child(4)"
  );
  if (durationCell) {
    const { duration_min: min, duration_max: max } = updateResult;
    durationCell.textContent =
      min && max && min != max ? `${min}'-${max}'` : max ? `${max}'` : "";
  }
}

function updateSpeechLogCard(logId, updateResult, payload) {
  const card = document.getElementById(`log-card-${logId}`);
  if (!card) return;

  if (payload.session_type_title !== "Individual Evaluator") {
    // Helper to safely set text content if element exists
    const setSafeText = (selector, text) => {
      const el = card.querySelector(selector);
      if (el) el.innerText = text;
    };

    setSafeText(".speech-title", `"${updateResult.session_title.replace(/"/g, "")}"`);
    setSafeText(".role-title", updateResult.session_title.replace(/"/g, "") + (updateResult.project_code ? ` (${updateResult.project_code})` : ""));
    
    setSafeText(".project-name", updateResult.project_name || "N/A");
    
    let code = updateResult.project_code
      ? `(${updateResult.project_code})`
      : "";
    if (updateResult.project_id == ProjectID.GENERIC) code = "(TM1.0)";
    
    setSafeText(".project-code", code);
    setSafeText(".pathway-info", updateResult.pathway || "N/A");
  }

  let mediaLink = card.querySelector(".btn-play");
  const newMediaUrl = payload.media_url;
  if (newMediaUrl) {
    if (!mediaLink) {
      mediaLink = document.createElement("a");
      mediaLink.href = newMediaUrl;
      mediaLink.target = "_blank";
      mediaLink.className = "icon-btn btn-play";
      mediaLink.title = "Watch Media";
      mediaLink.innerHTML = '<i class="fas fa-play-circle"></i>';
      card.querySelector(".card-actions").prepend(mediaLink);
    }
    mediaLink.href = newMediaUrl;
  } else if (mediaLink) {
    mediaLink.remove();
  }
}

// --- Event Listeners ---
document.addEventListener("DOMContentLoaded", () => {
  modalElements.form.addEventListener("submit", saveEditDetailsChanges);
  modalElements.pathwaySelect.addEventListener("change", updateDynamicOptions);
  modalElements.levelSelect.addEventListener("change", updateDynamicOptions);
  if (modalElements.isProjectCheckbox) {
    modalElements.isProjectCheckbox.addEventListener("change", (e) =>
      toggleGeneric(!e.target.checked)
    );
  }
});
