import { Injectable, signal } from '@angular/core';
import { AuthService } from './auth.service';

export interface DocumentInfo {
  id: number;
  filename: string;
  created_at: string;
}

const API_BASE = '/api/documents';

@Injectable({ providedIn: 'root' })
export class DocumentsService {
  documents = signal<DocumentInfo[]>([]);
  uploading = signal(false);
  error = signal('');

  constructor(private auth: AuthService) {}

  private authHeader(): Record<string, string> {
    return { Authorization: `Bearer ${this.auth.token()}` };
  }

  async refresh(): Promise<void> {
    try {
      const res = await fetch(API_BASE, { headers: this.authHeader() });
      if (!res.ok) throw new Error(`Failed to load documents: ${res.status}`);
      this.documents.set(await res.json());
    } catch {
      this.error.set('Could not load documents.');
    }
  }

  async upload(file: File): Promise<void> {
    this.error.set('');
    this.uploading.set(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        headers: this.authHeader(),
        body: formData,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `Upload failed: ${res.status}`);
      }
      await this.refresh();
    } catch (err: any) {
      this.error.set(err.message ?? 'Upload failed.');
    } finally {
      this.uploading.set(false);
    }
  }

  async remove(id: number): Promise<void> {
    try {
      const res = await fetch(`${API_BASE}/${id}`, {
        method: 'DELETE',
        headers: this.authHeader(),
      });
      if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
      this.documents.update(docs => docs.filter(d => d.id !== id));
    } catch {
      this.error.set('Could not delete document.');
    }
  }
}
