import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

const API_BASE = '/api/auth';
const TOKEN_KEY = 'claude_chat_token';

@Injectable({ providedIn: 'root' })
export class AuthService {
  token = signal<string | null>(this.readStoredToken());

  constructor(private http: HttpClient) {}

  private readStoredToken(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  }

  async login(email: string, password: string): Promise<void> {
    const res = await firstValueFrom(
      this.http.post<{ access_token: string }>(`${API_BASE}/login`, { email, password }),
    );
    this.setToken(res.access_token);
  }

  async register(email: string, password: string): Promise<void> {
    await firstValueFrom(this.http.post(`${API_BASE}/register`, { email, password }));
    await this.login(email, password);
  }

  logout(): void {
    this.setToken(null);
  }

  private setToken(token: string | null): void {
    this.token.set(token);
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    } catch {
      // localStorage unavailable (private browsing, etc.) - token still held in memory
    }
  }
}
