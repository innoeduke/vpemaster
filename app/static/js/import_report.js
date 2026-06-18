
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const fileInfo = document.getElementById('selected-file-info');
  const fileNameText = document.getElementById('file-name-text');
  const submitBtn = document.getElementById('submit-btn');

  if (dropZone && fileInput) {
    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      dropZone.addEventListener(eventName, preventDefaults, false);
      document.body.addEventListener(eventName, preventDefaults, false);
    });

    // Highlight drop zone when item is dragged over it
    ['dragenter', 'dragover'].forEach(eventName => {
      dropZone.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropZone.addEventListener(eventName, unhighlight, false);
    });

    // Handle dropped files
    dropZone.addEventListener('drop', handleDrop, false);

    // Handle selected files via input
    fileInput.addEventListener('change', handleFileSelect, false);
  }

  function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  function highlight(e) {
    dropZone.style.borderColor = '#004165';
    dropZone.style.background = '#f8fafc';
  }

  function unhighlight(e) {
    dropZone.style.borderColor = '#cbd5e1';
    dropZone.style.background = '#fff';
  }

  function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length > 0) {
      fileInput.files = files;
      updateFileInfo(files[0].name);
    }
  }

  function handleFileSelect(e) {
    if (fileInput.files.length > 0) {
      updateFileInfo(fileInput.files[0].name);
    }
  }

  function updateFileInfo(name) {
    fileNameText.textContent = name;
    fileInfo.style.display = 'inline-flex';
    submitBtn.style.display = 'inline-flex';
  }
