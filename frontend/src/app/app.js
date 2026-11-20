import { __decorate } from "tslib";
import { Component, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { NavBar } from './components/nav-bar/nav-bar';
import { Footer } from './components/footer/footer';
let App = class App {
    title = signal('Kasyno Edu');
};
App = __decorate([
    Component({
        selector: 'app-root',
        imports: [RouterOutlet, NavBar, Footer],
        templateUrl: './app.html',
        styleUrl: './app.css',
    })
], App);
export { App };
