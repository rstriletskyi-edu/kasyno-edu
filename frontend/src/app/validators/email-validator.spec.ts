import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { FormControl, FormsModule, NgModel } from '@angular/forms';
import { By } from '@angular/platform-browser';

import { EmailTldValidatorDirective, emailTldValidator } from './email-validator';

describe('emailTldValidator', () => {
  const validate = (value: unknown) => emailTldValidator()(new FormControl(value));

  it.each([
    'user@example.com',
    'first.last+tag@sub.example.co.uk',
    'a@b.pl',
    'user@example.museum',
    'user@example.xn--p1ai',
  ])('accepts %s', (email) => {
    expect(validate(email)).toBeNull();
  });

  it.each([
    'user@localhost',
    'user@example',
    'user@example.c',
    'user@example.123',
    'user@',
    'userexample.com',
  ])('rejects %s', (email) => {
    expect(validate(email)).toEqual({ emailTld: true });
  });

  it('ignores empty values (handled by required)', () => {
    expect(validate('')).toBeNull();
    expect(validate(null)).toBeNull();
  });
});

@Component({
  imports: [FormsModule, EmailTldValidatorDirective],
  template: `<input name="email" [(ngModel)]="value" email emailTld />`,
})
class Host {
  value = '';
}

describe('email + emailTld on an ngModel input', () => {
  const errorsFor = async (value: string) => {
    const fixture = TestBed.createComponent(Host);
    fixture.componentInstance.value = value;
    fixture.detectChanges();
    await fixture.whenStable();
    return fixture.debugElement.query(By.directive(NgModel)).injector.get(NgModel).errors;
  };

  it('flags bad syntax through the built-in validator', async () => {
    expect(await errorsFor('us er@example.com')).toEqual({ email: true });
  });

  it('flags a missing top-level domain through the custom validator', async () => {
    expect(await errorsFor('user@localhost')).toEqual({ emailTld: true });
  });

  it('accepts a valid address', async () => {
    expect(await errorsFor('user@example.com')).toBeNull();
  });
});
