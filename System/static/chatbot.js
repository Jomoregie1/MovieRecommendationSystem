console.log('chatbot.js is loaded');

function appendMessage(className, messageText, movieImageUrl = null) {
    console.log(`Appending message: className = ${className}, messageText = ${messageText}`);

    // Create a new message container element
    var messageContainerElement = $('<div></div>');
    messageContainerElement.addClass('message-container');
    if (className === 'user-message') {
        messageContainerElement.addClass('user');
    }

    // Create a new message element
    var messageElement = $('<div></div>');
    messageElement.addClass('message');
    messageElement.addClass(className);
    messageElement.text(messageText);

    // Append the message to the message container
    messageContainerElement.append(messageElement);

    // If a movie poster URL is provided, create an img element and append it below the message
    if (movieImageUrl) {
        var imageElement = $('<img>');
        imageElement.addClass('movie-poster');
        imageElement.attr('src', movieImageUrl);
        messageContainerElement.append(imageElement);
    }

    // Append the message container to the chat container
    $('#chat-container').append(messageContainerElement);

    // Scroll to the bottom of the chat container
    $('#chat-container').scrollTop($('#chat-container')[0].scrollHeight);
}

$(document).ready(function () {
    console.log('Document is ready');

    $('#message-form').submit(function (event) {
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
            success: function (data) {
                console.log('Chatbot response:', data);

                // Handle the chatterbot's response
                if (data.status === 'success') {
                    appendMessage('chatbot-message', data.response, data.movie_image_url);
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