// Fix for: Uncaught (in promise) TypeError: Cannot set properties of null (setting 'value')
// Added null check before setting value property

function setValueSafely(selector, value) {
    const element = document.querySelector(selector);
    if (element) {
        element.value = value;
    } else {
        console.warn(`Element with selector "${selector}" not found`);
    }
}

// Example usage (replace your current line 133):
// Instead of: document.getElementById('someId').value = someValue;
// Use: setValueSafely('#someId', someValue);

// Or if you prefer inline fix:
const targetElement = document.querySelector('#your-element-id'); // Replace with actual selector
if (targetElement) {
    targetElement.value = 'your-value'; // Replace with actual value
}