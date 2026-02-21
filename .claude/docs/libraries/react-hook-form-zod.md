# react-hook-form + zod

## Overview
- **react-hook-form**: Performant, flexible React form library with minimal re-renders
- **zod**: TypeScript-first schema validation library

## Version Info (2025)
- **react-hook-form**: v7.54.x
- **zod**: v3.24.x
- **@hookform/resolvers**: v3.9.x

## Installation
```bash
npm install react-hook-form zod @hookform/resolvers
```

## Basic Setup

### 1. Define Schema with Zod
```typescript
import { z } from 'zod'

const loginSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
})

type LoginFormValues = z.infer<typeof loginSchema>
```

### 2. Create Form Component
```tsx
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'

function LoginForm() {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  })
  
  const onSubmit = async (data: LoginFormValues) => {
    await fetch('/api/login', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }
  
  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <div>
        <label>Email</label>
        <input {...register('email')} />
        {errors.email && <span>{errors.email.message}</span>}
      </div>
      <div>
        <label>Password</label>
        <input type="password" {...register('password')} />
        {errors.password && <span>{errors.password.message}</span>}
      </div>
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Submitting...' : 'Login'}
      </button>
    </form>
  )
}
```

## Complex Forms

### 1. Nested Objects
```typescript
const addressSchema = z.object({
  street: z.string().min(1, 'Street is required'),
  city: z.string().min(1, 'City is required'),
  zipCode: z.string().regex(/^\d{5}$/, 'Invalid ZIP code'),
})

const userSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  email: z.string().email(),
  address: addressSchema,
})

type UserFormValues = z.infer<typeof userSchema>

function UserForm() {
  const { register, formState: { errors } } = useForm<UserFormValues>({
    resolver: zodResolver(userSchema),
  })
  
  return (
    <form>
      <input {...register('name')} />
      {errors.name && <span>{errors.name.message}</span>}
      
      <input {...register('email')} />
      {errors.email && <span>{errors.email.message}</span>}
      
      {/* Nested fields */}
      <input {...register('address.street')} />
      {errors.address?.street && <span>{errors.address.street.message}</span>}
      
      <input {...register('address.city')} />
      {errors.address?.city && <span>{errors.address.city.message}</span>}
    </form>
  )
}
```

### 2. Arrays (Dynamic Fields)
```typescript
const todoSchema = z.object({
  todos: z.array(
    z.object({
      id: z.string(),
      title: z.string().min(1, 'Title is required'),
      completed: z.boolean(),
    })
  ).min(1, 'Add at least one todo'),
})

type TodoFormValues = z.infer<typeof todoSchema>

function TodoForm() {
  const { register, formState: { errors } } = useForm<TodoFormValues>({
    resolver: zodResolver(todoSchema),
    defaultValues: {
      todos: [{ id: '1', title: '', completed: false }],
    },
  })
  
  return (
    <form>
      {fields.map((field, index) => (
        <div key={field.id}>
          <input {...register(`todos.${index}.title`)} />
          {errors.todos?.[index]?.title && (
            <span>{errors.todos[index]?.title?.message}</span>
          )}
        </div>
      ))}
    </form>
  )
}
```

### 3. Using useFieldArray for Dynamic Arrays
```tsx
import { useFieldArray } from 'react-hook-form'

function DynamicForm() {
  const { control, register, formState: { errors } } = useForm<{
    users: Array<{ name: string; email: string }>
  }>({
    defaultValues: {
      users: [{ name: '', email: '' }],
    },
  })
  
  const { fields, append, remove } = useFieldArray({
    control,
    name: 'users',
  })
  
  return (
    <form>
      {fields.map((field, index) => (
        <div key={field.id}>
          <input {...register(`users.${index}.name`)} />
          <input {...register(`users.${index}.email`)} />
          <button type="button" onClick={() => remove(index)}>
            Remove
          </button>
        </div>
      ))}
      <button type="button" onClick={() => append({ name: '', email: '' })}>
        Add User
      </button>
    </form>
  )
}
```

## Advanced Zod Schemas

### 1. Conditional Validation
```typescript
const schema = z.object({
  hasAccount: z.boolean(),
  email: z.string().optional(),
  password: z.string().optional(),
}).refine(
  (data) => !data.hasAccount || (data.email && data.password),
  { message: 'Email and password required when hasAccount is true' }
)
```

### 2. Custom Validation
```typescript
const schema = z.object({
  password: z.string()
    .min(8, 'Password must be at least 8 characters')
    .regex(/[A-Z]/, 'Must contain uppercase letter')
    .regex(/[a-z]/, 'Must contain lowercase letter')
    .regex(/[0-9]/, 'Must contain number'),
  confirmPassword: z.string(),
}).refine(
  (data) => data.password === data.confirmPassword,
  { message: 'Passwords do not match', path: ['confirmPassword'] }
)
```

### 3. Transformed Values
```typescript
const schema = z.object({
  amount: z.string().transform((val) => parseFloat(val)),
  date: z.string().transform((val) => new Date(val)),
  // Transform before validation
  email: z.string()
    .transform(val => val.toLowerCase())
    .pipe(z.string().email()),
})
```

### 4. Enums and Unions
```typescript
const schema = z.object({
  role: z.enum(['user', 'admin', 'superadmin']),
  contactMethod: z.discriminatedUnion('type', [
    z.object({ type: z.literal('email'), email: z.string().email() }),
    z.object({ type: z.literal('phone'), phone: z.string() }),
  ]),
})
```

## Form Best Practices

### 1. Server Action Integration
```tsx
'use client'

import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'

async function createTodo(data: TodoFormValues) {
  'use server'
  // Server action
}

function TodoForm() {
  const { register, handleSubmit } = useForm({
    resolver: zodResolver(todoSchema),
  })
  
  return (
    <form action={handleSubmit(createTodo)}>
      <input {...register('title')} />
      <button type="submit">Create</button>
    </form>
  )
}
```

### 2. Reset Form with Server Data
```tsx
function EditUser({ user }: { user: User }) {
  const { reset, register, handleSubmit } = useForm({
    resolver: zodResolver(userSchema),
    values: user, // Reset form with user data
  })
  
  const onSuccess = (data: User) => {
    reset(data) // Update form with server response
  }
  
  return <form onSubmit={handleSubmit(onSuccess)}>...</form>
}
```

### 3. Optimistic UI
```tsx
function TodoForm() {
  const { register, handleSubmit, reset } = useForm()
  const queryClient = useQueryClient()
  
  const onSubmit = async (data: TodoFormValues) => {
    // Optimistic update
    queryClient.setQueryData(['todos'], (old) => [...old, data])
    
    try {
      await createTodo(data)
      reset()
    } catch (error) {
      // Rollback on error
      queryClient.invalidateQueries(['todos'])
    }
  }
  
  return <form onSubmit={handleSubmit(onSubmit)}>...</form>
}
```

## UI Library Integration

### 1. shadcn/ui Integration
```tsx
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Form, FormField, FormItem, FormLabel, FormControl, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

function ShadcnForm() {
  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  })
  
  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)}>
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl>
                <Input placeholder="email@example.com" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit">Submit</Button>
      </form>
    </Form>
  )
}
```

## Common Pitfalls

### 1. Not Resetting Form After Submit
```tsx
// ✅ Reset after successful submit
const onSubmit = async (data) => {
  await submitData(data)
  reset() // Clear form
}
```

### 2. Missing Type Inference
```tsx
// ❌ Manual typing
const { register } = useForm<{ email: string }>()

// ✅ Infer from schema
type FormValues = z.infer<typeof schema>
const { register } = useForm<FormValues>({
  resolver: zodResolver(schema),
})
```

### 3. Not Handling Async Validation
```tsx
const schema = z.object({
  username: z.string()
    .refine(async (username) => {
      const res = await fetch(`/api/check-username/${username}`)
      return !await res.json().exists
    }, 'Username already taken'),
})
```

## Official Resources
- [react-hook-form Documentation](https://www.react-hook-form.com/)
- [Zod Documentation](https://zod.dev/)
- [@hookform/resolvers](https://github.com/react-hook-form/resolvers)
