import { Component, OnInit, inject, signal } from '@angular/core';
import { SlotsClient } from '../../../../../services/games-clients/slots-client';

@Component({
  imports: [],
  selector: 'slots',
  styleUrl: './slots.css',
  templateUrl: './slots.html',
})
export class Slots implements OnInit {
  private readonly client = inject(SlotsClient);

  protected readonly loading = signal<boolean>(false);
  protected readonly error = signal<boolean>(false);
  protected readonly errorMessage = signal<string>('');

  ngOnInit() {}
}
