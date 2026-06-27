// AgentPlane — Chat component
// WebSocket chat with agent, message copy, command formatting
// Messages persist across view switches within a session

var _chatMessageStore = [];
var CHAT_MAX_MESSAGES = 200;

function _trimChatMessages(msgs) {
  if (msgs.length > CHAT_MAX_MESSAGES) {
    msgs.splice(0, msgs.length - CHAT_MAX_MESSAGES);
  }
}

function _renderChatMessage(text) {
  if (!text) return '';
  var escaped = escapeHtml(text);
  // Code blocks: ```...```
  escaped = escaped.replace(/```([\s\S]*?)```/g, '<code class="chat-code-block">$1</code>');
  // Inline code: `...`
  escaped = escaped.replace(/`([^`]+)`/g, '<code class="chat-code-inline">$1</code>');
  return escaped;
}

const ChatComponent = {
  template: `
    <div class="chat-container" style="flex:1;">
      <div class="chat-messages" ref="chatMessagesEl" @scroll="onChatScroll">
        <div v-if="chatMessages.length === 0" class="chat-welcome">
          <h3>{{ t('chat.title') }}</h3>
          <p v-html="t('chat.welcome')"></p>
        </div>
        <div v-for="(msg, i) in chatMessages" :key="msg._id || i">
          <div v-if="getMessageDate(msg, i)" class="chat-date-separator">{{ getMessageDate(msg, i) }}</div>
          <div class="message" :class="msg.role">
            <div>
              <div v-if="msg.rejected" class="message-rejected">{{ msg.text }}</div>
              <div v-else-if="msg.error" class="message-error">{{ msg.text }}</div>
              <div v-else class="message-bubble">
                <pre class="message-text" v-html="renderMessage(msg.text)"></pre>
                <button v-if="msg.role === 'agent'" class="msg-copy-btn" @click="copyMessage(msg)" :title="t('action.copy')">
                  {{ msg._copied ? '\\u2713' : '\\u2398' }}
                </button>
              </div>
              <div class="message-time">{{ msg.time }}</div>
            </div>
          </div>
        </div>
        <div v-if="agentTyping" class="message agent">
          <div>
            <div class="typing">
              <div class="typing-dot"></div>
              <div class="typing-dot"></div>
              <div class="typing-dot"></div>
            </div>
            <div class="message-time">{{ t('chat.processing') }}</div>
          </div>
        </div>
      </div>
      <button v-if="showScrollBtn" class="chat-scroll-btn" @click="scrollToBottom" :aria-label="'Scroll to bottom'">&#x25BC;</button>
      <div class="chat-input-area">
        <button v-if="chatMessages.length > 0" class="btn-ghost btn-sm" @click="clearChat" :title="t('chat.clear')" style="flex-shrink:0;">
          {{ t('chat.clear') }}
        </button>
        <textarea class="chat-input" v-model="chatInput" ref="chatInputEl"
                  :placeholder="t('chat.placeholder')"
                  @keydown="handleChatKeydown"
                  @input="autoResize"
                  rows="1"></textarea>
        <button class="chat-send" @click="sendMessage" :disabled="!chatInput.trim() || agentTyping">
          {{ t('action.send') }}
        </button>
      </div>
    </div>
  `,

  setup() {
    const { t } = useI18n();
    const chatMessages = ref(_chatMessageStore);
    const chatInput = ref('');
    const agentTyping = ref(false);
    const chatMessagesEl = ref(null);
    const chatInputEl = ref(null);
    const showScrollBtn = ref(false);
    let _chatId = _chatMessageStore.length;

    // Persist messages across view switches
    Vue.watch(chatMessages, (val) => { _chatMessageStore = val; }, { deep: true });

    function onChatScroll() {
      if (!chatMessagesEl.value) return;
      var el = chatMessagesEl.value;
      var atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
      showScrollBtn.value = !atBottom;
    }

    function scrollToBottom() {
      if (chatMessagesEl.value) {
        chatMessagesEl.value.scrollTop = chatMessagesEl.value.scrollHeight;
        showScrollBtn.value = false;
      }
    }

    function autoResize() {
      const el = chatInputEl.value;
      if (el) {
        el.style.height = 'auto';
        el.style.height = Math.min(el.scrollHeight, 120) + 'px';
      }
    }

    function handleChatKeydown(e) {
      // Enter without Shift sends; Shift+Enter inserts newline
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    }

    function copyMessage(msg) {
      copyToClipboard(msg.text).then(ok => {
        if (ok) {
          msg._copied = true;
          showToast(t('toast.copied'), 'success', 1500);
          setTimeout(() => { msg._copied = false; }, 2000);
        }
      });
    }

    function clearChat() {
      chatMessages.value = [];
      _chatMessageStore = [];
      _chatId = 0;
    }

    function getMessageDate(msg, idx) {
      if (!msg.time) return '';
      var msgDate = msg.time.split(',')[0] || msg.time;
      if (idx === 0) return msgDate;
      var prev = chatMessages.value[idx - 1];
      var prevDate = prev.time ? (prev.time.split(',')[0] || prev.time) : '';
      return msgDate !== prevDate ? msgDate : '';
    }

    function onWsMessage(event) {
      const msg = event.detail;

      if (msg.type === 'chat_response' && msg.payload?.status === 'running') {
        agentTyping.value = true;
        return;
      }

      agentTyping.value = false;

      if (msg.type === 'command_result') {
        const output = msg.payload?.output || {};
        const items = output.items || [];
        let text = '';
        if (items.length > 0) {
          text = items.map(it => {
            const parts = [`${it.app} (${it.target})`];
            if (it.control_plane) parts.push(`control: ${it.control_plane}`);
            if (it.public_url) parts.push(it.public_url);
            return parts.join(' | ');
          }).join('\n');
        } else if (output.hosts) {
          text = output.hosts.map(h =>
            `${h.hostname} (${h.target}): ${h.status} ${h.ip || 'local'}`
          ).join('\n');
        } else if (output.operations) {
          text = output.operations.slice(0, 5).map(op =>
            `${op.object_type} ${op.action} -> ${op.result} (${op.target})`
          ).join('\n');
        } else {
          text = JSON.stringify(output, null, 2);
        }
        chatMessages.value.push({
          role: 'agent',
          text: `> ${msg.payload?.command || 'result'}\n${text}`,
          time: new Date().toLocaleTimeString(),
          _id: ++_chatId,
        });
      } else if (msg.type === 'command_rejected') {
        chatMessages.value.push({
          role: 'agent',
          text: msg.payload?.reason || t('chat.blocked'),
          rejected: true,
          time: new Date().toLocaleTimeString(),
          _id: ++_chatId,
        });
      } else if (msg.type === 'error') {
        chatMessages.value.push({
          role: 'agent',
          text: msg.payload?.reason || msg.payload?.message || t('chat.error'),
          error: true,
          time: new Date().toLocaleTimeString(),
          _id: ++_chatId,
        });
      }

      _trimChatMessages(chatMessages.value);

      Vue.nextTick(() => {
        if (chatMessagesEl.value) {
          var el = chatMessagesEl.value;
          var atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
          if (atBottom) {
            el.scrollTop = el.scrollHeight;
          }
        }
      });
    }

    Vue.onMounted(() => {
      window.addEventListener('ap-ws-message', onWsMessage);
    });

    Vue.onUnmounted(() => {
      window.removeEventListener('ap-ws-message', onWsMessage);
    });

    function sendMessage() {
      const text = chatInput.value.trim();
      if (!text || agentTyping.value) return;

      chatMessages.value.push({
        role: 'user',
        text,
        time: new Date().toLocaleTimeString(),
        _id: ++_chatId,
      });
      _trimChatMessages(chatMessages.value);
      chatInput.value = '';
      Vue.nextTick(() => {
        if (chatInputEl.value) {
          chatInputEl.value.style.height = 'auto';
        }
      });

      window.dispatchEvent(new CustomEvent('ap-send-chat', { detail: { text } }));

      Vue.nextTick(() => {
        if (chatMessagesEl.value) {
          chatMessagesEl.value.scrollTop = chatMessagesEl.value.scrollHeight;
        }
      });
    }

    return {
      chatMessages, chatInput, agentTyping, chatMessagesEl, chatInputEl,
      showScrollBtn, scrollToBottom, onChatScroll,
      sendMessage, autoResize, handleChatKeydown, copyMessage, clearChat,
      getMessageDate,
      renderMessage: _renderChatMessage, t,
    };
  },
};
