import { __decorate } from "tslib";
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { environment } from '../../environments/environment';
let HealthService = class HealthService {
    http = inject(HttpClient);
    getHealth() {
        return this.http.get(`${environment.apiUrl}/health`);
    }
};
HealthService = __decorate([
    Injectable({ providedIn: 'root' })
], HealthService);
export { HealthService };
