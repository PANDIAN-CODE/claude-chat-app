import { Component } from '@angular/core';
import { ChatComponent } from './chat.component';
import { LoginComponent } from './login.component';
import { AuthService } from './auth.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [ChatComponent, LoginComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css'
})
export class AppComponent {
  title = 'frontend';

  constructor(public auth: AuthService) {}
}
