// AgentPlane — Chat component
// WebSocket chat with agent

const ChatComponent = {
  template: `
    <div class="chat-container" style="flex:1;">
      <div class="chat-messages" ref="chatMessagesEl">
        <div v-if="chatMessages.length === 0" class="chat-welcome">
          <h3>{{ t('chat.title') }}</h3>
          <p v-html="t('chat.welcome')"></p>
        </div>
        <div v-for="(msg, i) in chatMessages" :key="i" class="message" :class="msg.role">
          <div>
            <div v-if="msg.rejected" class="message-rejected">{{ msg.text }}</div>
            <div v-else-if="msg.error" class="message-error">{{ msg.text }}</div>
            <div v-else class="message-bubble">{{ msg.text }}</div>
            <div class="message-time">{{ msg.time }}</div>
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
      <div class="chat-input-area">
        <textarea class="chat-input" v-model="chatInput" ref="chatInputEl"
                  :placeholder="t('chat.placeholder')"
                  @keydown.enter.exact.prevent="sendMessage"
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
    const chatMessages = ref([]);
    const chatInput = ref('');
    const agentTyping = ref(false);
    const chatMessagesEl = ref(null);
    const chatInputEl = ref(null);

    function autoResize() {
      const el = chatInputEl.value;
      if (el) {
        el.style.height = 'auto';
        el.style.height = Math.min(el.scrollHeight, 120) + 'px';
      }
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
        });
      } else if (msg.type === 'command_rejected') {
        chatMessages.value.push({
          role: 'agent',
          text: msg.payload?.reason || t('chat.blocked'),
          rejected: true,
          time: new Date().toLocaleTimeString(),
        });
      } else if (msg.type === 'error') {
        chatMessages.value.push({
          role: 'agent',
          text: msg.payload?.reason || msg.payload?.message || t('chat.error'),
          error: true,
          time: new Date().toLocaleTimeString(),
        });
      }

      Vue.nextTick(() => {
        if (chatMessagesEl.value) {
          chatMessagesEl.value.scrollTop = chatMessagesEl.value.scrollHeight;
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
      });
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
      sendMessage, autoResize, t,
    };
  },
};
