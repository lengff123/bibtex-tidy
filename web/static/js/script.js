// JavaScript code for handling editor and sidebar interactions will go here.

document.addEventListener('DOMContentLoaded', function() {
    const runButton = document.createElement('button');
    runButton.textContent = 'Run Code';
    document.body.appendChild(runButton);

    runButton.addEventListener('click', function() {
        const code = editor.getValue();

        fetch('/run', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ code: code })
        })
        .then(response => response.json())
        .then(data => {
            if (data.output) {
                alert('Output: ' + data.output);
            } else if (data.error) {
                alert('Error: ' + data.error);
            }
        })
        .catch(error => console.error('Error:', error));
    });
});
