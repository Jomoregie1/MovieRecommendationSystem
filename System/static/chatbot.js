console.log('chatbot.js is loaded');

function appendMessage(className, messageText) {
    console.log(`Appending message: className = ${className}, messageText = ${messageText}`);

    // Create a new message element
    var messageElement = $('<div></div>');
    messageElement.addClass('message');
    messageElement.addClass(className);
    messageElement.text(messageText);

    // Append the message to the chat container
    $('#chat-container').append(messageElement);

    // Scroll to the bottom of the chat container
    $('#chat-container').scrollTop($('#chat-container')[0].scrollHeight);
}

$(document).ready(function() {
    console.log('Document is ready');

    $('#message-form').submit(function(event) {
        console.log('Form submitted');
        event.preventDefault();

        // Get the user's message from the input field
        var userMessage = $('#message-input').val().trim();

        // Send an AJAX request to the server
        $.ajax({
            url: '/chat',
            type: 'POST',
            data: {
                message: userMessage,
                user_id: '{{ current_user.id }}' // Include the user ID in the request data
            },
            success: function(response) {
                console.log('Chatbot response:', response);

                // Handle the chatterbot's response
                if (response.status === 'success') {
                    appendMessage('chatbot-message', response.response);
                } else {
                    console.error('Error: Chatbot response status is not success.');
                }
            }
        });

        // Clear the input field
        $('#message-input').val('');

        // Display the user's message on the page
        appendMessage('user-message', userMessage);
    });
});