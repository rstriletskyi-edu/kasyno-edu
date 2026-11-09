import { Component, signal } from '@angular/core';
import { GameSection } from '../game-section/game-section';
import { LearningSection } from '../learning-section/learning-section';
import { NavBar } from '../nav-bar/nav-bar';

@Component({
  imports: [GameSection, LearningSection, NavBar],
  selector: 'homepage',
  styleUrl: './homepage.css',
  templateUrl: './homepage.html',
})
export class Homepage {}
