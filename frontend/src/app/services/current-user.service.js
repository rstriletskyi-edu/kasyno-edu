import { __decorate } from "tslib";
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { environment } from '../../environments/environment';
let CurrentUserService = class CurrentUserService {
    http = inject(HttpClient);
    getMe() {
        return this.http.get(`${environment.apiUrl}/auth/me`);
    }
};
CurrentUserService = __decorate([
    Injectable({ providedIn: 'root' })
], CurrentUserService);
export { CurrentUserService };
