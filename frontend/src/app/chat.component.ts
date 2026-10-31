import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { marked } from 'marked';
import { AuthService } from './auth.service';
import { DocumentsService } from './documents.service';

interface Citation {
  document_id: number;
  filename: string;
}

interface Msg {
  role: 'user' | 'assistant';
  text: string;
  streaming?: boolean;
  citations?: Citation[];
}

const API_BASE = '/api/chat';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="box">
      <div class="header">
        <span>Claude Assistant</span>
        <button class="logout" (click)="auth.logout()">Log out</button>
      </div>

      <div class="docs">
        <div class="docs-header">
          <span>Documents</span>
          <label class="upload-btn">
            + Upload PDF
            <input type="file" accept="application/pdf" hidden
                   (change)="onFileSelected($event)" [disabled]="docs.uploading()" />
          </label>
        </div>
        @if (docs.uploading()) { <div class="docs-status">Uploading...</div> }
        @if (docs.error()) { <div class="docs-status error-text">{{ docs.error() }}</div> }
        @if (docs.documents().length > 0) {
          <div class="docs-list">
            @for (d of docs.documents(); track d.id) {
              <span class="doc-chip">
                {{ d.filename }}
                <button (click)="docs.remove(d.id)" title="Remove">×</button>
              </span>
            }
          </div>
        }
      </div>

      <div class="chat">
        @for (m of messages(); track $index) {
          <div class="row" [class.me]="m.role === 'user'">
            <div class="bubble" [class.user]="m.role === 'user'">
              @if (m.role === 'assistant') {
                <span [innerHTML]="render(m.text)"></span>
                @if (m.streaming) { <span class="cursor">▍</span> }
                @if (m.citations && m.citations.length > 0) {
                  <div class="citations">
                    Sources: {{ citationNames(m.citations) }}
                  </div>
                }
              } @else {
                {{ m.text }}
              }
            </div>
          </div>
        }
      </div>

      @if (error()) {
        <div class="error">
          {{ error() }}
          <button class="retry" (click)="retry()">Retry</button>
        </div>
      }

      <div class="bar">
        <input [(ngModel)]="input" (keyup.enter)="send()"
               maxlength="2000" placeholder="Type your question..."
               [disabled]="loading()" />
        @if (loading()) {
          <button class="stop" (click)="stop()">Stop</button>
        } @else {
          <button (click)="send()" [disabled]="!input.trim()">Send</button>
        }
      </div>
    </div>
  `,
  styles: [`
    .box { max-width: 600px; margin: 30px auto; border: 1px solid #d0d7de;
           border-radius: 10px; font-family: Arial, sans-serif; overflow: hidden; }
    .header { background: #d97757; color: #fff; padding: 12px 16px; font-weight: bold;
              display: flex; justify-content: space-between; align-items: center; }
    .header .logout { background: transparent; border: 1px solid #fff; color: #fff;
                       padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: normal;
                       cursor: pointer; }
    .docs { padding: 8px 12px; border-bottom: 1px solid #d0d7de; background: #fafafa; }
    .docs-header { display: flex; justify-content: space-between; align-items: center;
                    font-size: 13px; font-weight: bold; color: #555; }
    .upload-btn { font-size: 12px; font-weight: normal; color: #d97757; cursor: pointer;
                  border: 1px solid #d97757; padding: 3px 8px; border-radius: 6px; }
    .docs-status { font-size: 12px; color: #888; margin-top: 4px; }
    .docs-status.error-text { color: #c0392b; }
    .docs-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
    .doc-chip { background: #fff; border: 1px solid #e1e4e8; border-radius: 12px;
                padding: 3px 8px; font-size: 12px; display: flex; align-items: center; gap: 4px; }
    .doc-chip button { border: 0; background: transparent; cursor: pointer; color: #999;
                        font-size: 14px; line-height: 1; padding: 0; }
    .chat { height: 320px; overflow-y: auto; padding: 12px; background: #f6f8fa; }
    .row { display: flex; margin-bottom: 8px; }
    .row.me { justify-content: flex-end; }
    .bubble { max-width: 75%; padding: 8px 12px; border-radius: 12px;
              background: #fff; border: 1px solid #e1e4e8; white-space: pre-wrap; }
    .bubble :global(p) { margin: 0 0 8px; }
    .bubble :global(p:last-child) { margin-bottom: 0; }
    .bubble :global(pre) { background: #f0f0f0; padding: 8px; border-radius: 6px; overflow-x: auto; }
    .bubble :global(code) { font-family: monospace; }
    .bubble.user { background: #d97757; color: #fff; border-color: #d97757; }
    .citations { margin-top: 6px; font-size: 11px; color: #888; font-style: italic; }
    .cursor { animation: blink 1s step-start infinite; }
    @keyframes blink { 50% { opacity: 0; } }
    .bar { display: flex; gap: 8px; padding: 10px; border-top: 1px solid #d0d7de; }
    .bar input { flex: 1; padding: 10px; border: 1px solid #ccc; border-radius: 6px; }
    .bar button { padding: 10px 18px; border: 0; border-radius: 6px;
                  background: #d97757; color: #fff; cursor: pointer; }
    .bar button:disabled { opacity: 0.5; cursor: not-allowed; }
    .bar button.stop { background: #6a6a6a; }
    .error { color: #c0392b; padding: 8px 12px; font-size: 14px;
              display: flex; align-items: center; gap: 8px; }
    .error .retry { padding: 4px 10px; border: 1px solid #c0392b; background: #fff;
                     color: #c0392b; border-radius: 6px; cursor: pointer; font-size: 13px; }
  `],
})
export class ChatComponent implements OnInit {
  input = '';
  messages = signal<Msg[]>([]);
  loading = signal(false);
  error = signal('');

  private conversationId: number | null = null;
  private abortController?: AbortController;

  constructor(public auth: AuthService, public docs: DocumentsService) {}

  async ngOnInit() {
    this.docs.refresh();

    try {
      const conversations = await this.authedJson<{ id: number }[]>(
        `${API_BASE}/conversations`,
      );
      if (conversations.length > 0) {
        this.conversationId = conversations[0].id;
        const history = await this.authedJson<{ role: 'user' | 'assistant'; content: string }[]>(
          `${API_BASE}/conversations/${this.conversationId}/messages`,
        );
        this.messages.set(history.map(m => ({ role: m.role, text: m.content })));
        return;
      }
    } catch {
      // fall through to greeting below if history can't be loaded
    }
    this.messages.set([{ role: 'assistant', text: 'Hello! How can I help you?' }]);
  }

  render(text: string): string {
    return marked.parse(text, { async: false }) as string;
  }

  citationNames(citations: Citation[]): string {
    return citations.map(c => c.filename).join(', ');
  }

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) this.docs.upload(file);
    input.value = '';
  }

  send() {
    const text = this.input.trim();
    if (!text || this.loading()) return;

    this.messages.update(m => [...m, { role: 'user', text }]);
    this.input = '';
    this.streamReply(text);
  }

  retry() {
    const lastUser = [...this.messages()].reverse().find(m => m.role === 'user');
    if (!lastUser) return;
    this.error.set('');
    this.streamReply(lastUser.text);
  }

  stop() {
    this.abortController?.abort();
  }

  private async streamReply(message: string) {
    this.error.set('');
    this.loading.set(true);

    this.messages.update(m => [...m, { role: 'assistant', text: '', streaming: true }]);
    this.abortController = new AbortController();

    try {
      const res = await fetch(`${API_BASE}/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${this.auth.token()}`,
        },
        body: JSON.stringify({ conversation_id: this.conversationId, message }),
        signal: this.abortController.signal,
      });

      if (res.status === 401) {
        this.auth.logout();
        return;
      }
      if (!res.ok || !res.body) {
        throw new Error(`Backend returned ${res.status}`);
      }

      const convId = res.headers.get('X-Conversation-Id');
      if (convId) this.conversationId = Number(convId);

      const citationsHeader = res.headers.get('X-Citations');
      if (citationsHeader) {
        try {
          const citations: Citation[] = JSON.parse(citationsHeader);
          if (citations.length > 0) this.setLastAssistantCitations(citations);
        } catch {
          // malformed header - ignore, citations are a nice-to-have
        }
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        this.appendToLastAssistant(decoder.decode(value, { stream: true }));
      }
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        // user stopped the stream intentionally - keep partial text
      } else {
        this.error.set('Something went wrong. Check that the backend is running.');
        this.dropEmptyAssistant();
      }
    } finally {
      this.finishStreaming();
      this.loading.set(false);
    }
  }

  private async authedJson<T>(url: string): Promise<T> {
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${this.auth.token()}` },
    });
    if (!res.ok) throw new Error(`Request to ${url} failed: ${res.status}`);
    return res.json();
  }

  private appendToLastAssistant(chunk: string) {
    this.messages.update(m => {
      const copy = [...m];
      const last = copy[copy.length - 1];
      copy[copy.length - 1] = { ...last, text: last.text + chunk };
      return copy;
    });
  }

  private setLastAssistantCitations(citations: Citation[]) {
    this.messages.update(m => {
      const copy = [...m];
      const last = copy[copy.length - 1];
      copy[copy.length - 1] = { ...last, citations };
      return copy;
    });
  }

  private dropEmptyAssistant() {
    this.messages.update(m => {
      const last = m[m.length - 1];
      return last?.role === 'assistant' && last.text === '' ? m.slice(0, -1) : m;
    });
  }

  private finishStreaming() {
    this.messages.update(m => {
      const copy = [...m];
      const last = copy[copy.length - 1];
      if (last?.streaming) {
        copy[copy.length - 1] = { ...last, streaming: false };
      }
      return copy;
    });
  }
}
