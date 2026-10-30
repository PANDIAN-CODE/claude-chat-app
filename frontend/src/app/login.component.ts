import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from './auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="box">
      <div class="header">{{ mode() === 'login' ? 'Sign in' : 'Create account' }}</div>
      <div class="form">
        <input type="email" [(ngModel)]="email" placeholder="Email" (keyup.enter)="submit()" />
        <input type="password" [(ngModel)]="password" placeholder="Password" (keyup.enter)="submit()" />
        @if (error()) { <div class="error">{{ error() }}</div> }
        <button (click)="submit()" [disabled]="loading()">
          {{ mode() === 'login' ? 'Sign in' : 'Create account' }}
        </button>
        <a (click)="toggle()">
          {{ mode() === 'login' ? 'Need an account? Register' : 'Have an account? Sign in' }}
        </a>
      </div>
    </div>
  `,
  styles: [`
    .box { max-width: 320px; margin: 60px auto; border: 1px solid #d0d7de; border-radius: 10px;
           font-family: Arial, sans-serif; overflow: hidden; }
    .header { background: #d97757; color: #fff; padding: 12px 16px; font-weight: bold; }
    .form { padding: 16px; display: flex; flex-direction: column; gap: 10px; }
    input { padding: 10px; border: 1px solid #ccc; border-radius: 6px; font-size: 14px; }
    button { padding: 10px; border: 0; border-radius: 6px; background: #d97757; color: #fff; cursor: pointer; }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    a { color: #d97757; text-align: center; cursor: pointer; font-size: 13px; }
    .error { color: #c0392b; font-size: 13px; }
  `],
})
export class LoginComponent {
  mode = signal<'login' | 'register'>('login');
  email = '';
  password = '';
  loading = signal(false);
  error = signal('');

  constructor(private auth: AuthService) {}

  toggle() {
    this.mode.set(this.mode() === 'login' ? 'register' : 'login');
    this.error.set('');
  }

  async submit() {
    if (!this.email.trim() || !this.password.trim() || this.loading()) return;
    this.loading.set(true);
    this.error.set('');
    try {
      if (this.mode() === 'login') {
        await this.auth.login(this.email.trim(), this.password);
      } else {
        await this.auth.register(this.email.trim(), this.password);
      }
    } catch (err: any) {
      this.error.set(this.extractErrorMessage(err));
    } finally {
      this.loading.set(false);
    }
  }

  private extractErrorMessage(err: any): string {
    const detail = err?.error?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      // FastAPI/Pydantic validation errors: [{ loc, msg, type }, ...]
      return detail.map((d: any) => d.msg ?? JSON.stringify(d)).join('; ');
    }
    return 'Something went wrong. Check that the backend is running.';
  }
}
