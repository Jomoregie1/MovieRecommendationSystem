console.log('chatbot.js is loaded');

function initCloseButtons() {
  const closeButtons = document.querySelectorAll(".close");
  closeButtons.forEach((button) => {
    button.addEventListener("click", function () {
      this.parentElement.style.display = "none";
    });
  });
}

function getCurrentTimeString() {
  const now = new Date();
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  return `${hours}:${minutes}`;
}

function clearChat() {
  const chatContainer = document.getElementById('chat-container');
  chatContainer.innerHTML = '';
}

function appendMessage(cssClass, messageText, senderName, timestamp, imageURL) {

  $('.typing-indicator').remove();

  const chatContainer = document.getElementById('chat-container');

  const messageContainer = document.createElement('div');
  messageContainer.classList.add('message-container');

  const tailElement = document.createElement('div');
  tailElement.classList.add('msg-tail');

  if (cssClass === 'user-message') {
  messageContainer.classList.add('user');
  tailElement.classList.add('user-tail');
} else {
  tailElement.classList.add('chatbot-tail');
  }

  const messageElement = document.createElement('div');
  messageElement.classList.add('message');

  const msgBubbleElement = document.createElement('div');
  msgBubbleElement.classList.add('msg-bubble',cssClass);

  const msgInfoElement = document.createElement('div');
  msgInfoElement.classList.add('msg-info');

  const msgInfoNameElement = document.createElement('div');
  msgInfoNameElement.classList.add('msg-info-name');
  msgInfoNameElement.innerText = senderName;

  const msgInfoTimeElement = document.createElement('div');
  msgInfoTimeElement.classList.add('msg-info-time');
  msgInfoTimeElement.innerText = timestamp;

  const msgTextElement = document.createElement('div');
  msgTextElement.classList.add('msg-text');
  msgTextElement.innerText = messageText;

  msgInfoElement.appendChild(msgInfoNameElement);
  msgInfoElement.appendChild(msgInfoTimeElement);
  msgBubbleElement.appendChild(msgInfoElement);
  msgBubbleElement.appendChild(msgTextElement);
  msgBubbleElement.appendChild(tailElement);
  messageElement.appendChild(msgBubbleElement);


    if (imageURL) {
    const msgImageElement = document.createElement('img');
    msgImageElement.classList.add('msg-image');
    msgImageElement.src = imageURL;
    msgBubbleElement.appendChild(msgImageElement);
  }

  messageContainer.appendChild(messageElement);
  chatContainer.appendChild(messageContainer);

  // Scroll to the bottom of the chat container
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

$(document).ready(function () {
  console.log('Document is ready');

  initCloseButtons();

  $('#message-form').submit(function (event) {
    console.log('Form submitted');
    event.preventDefault();

    // Get the user's message from the input field
    var userMessage = $('#message-input').val().trim();

    // Check if the user's message is empty or contains only whitespace
    if (!userMessage) {
      console.log("Empty or whitespace-only message. Not sending.");
      return;
    }

    const user_name = $('#user-name').val() || 'User';
    const current_time = getCurrentTimeString();

    // Display the user's message on the page
    appendMessage('user-message', userMessage, user_name || 'User', current_time);

    // Create a typing indicator element
    var typingIndicatorElement = $('<div></div>');
    typingIndicatorElement.addClass('typing-indicator');
    typingIndicatorElement.append('<span></span><span></span><span></span>');

    // Append the typing indicator to the chat container
    $('#chat-container').append(typingIndicatorElement);

    // Send an AJAX request to the server
    $.ajax({
      url: '/',
      type: 'POST',
      data: {
        message: userMessage,
        user_id: '{{ current_user.id }}', // Include the user ID in the request data
      },
      success: function (data) {
        console.log('Chatbot response:', data);

    // Handle the chatterbot's response
    if (data.status === 'success') {
        const chatbot_name = 'Buddy';
        const current_time = getCurrentTimeString();
        appendMessage('chatbot-message', data.response, chatbot_name, current_time, data.movie_image_url);
        $('#user-name').val(user_name);
    } else {
        console.error('Error: Chatbot response status is not success.');
    }
    },
    });

    $('#clear-chat').on('click', function () {
  clearChat();
    });

    // Clear the input field
    $('#message-input').val('');


  });
});