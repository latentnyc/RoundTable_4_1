# Generated TypeScript README
This README will guide you through the process of using the generated JavaScript SDK package for the connector `example`. It will also provide examples on how to use your generated SDK to call your Data Connect queries and mutations.

**If you're looking for the `React README`, you can find it at [`dataconnect-generated/react/README.md`](./react/README.md)**

***NOTE:** This README is generated alongside the generated SDK. If you make changes to this file, they will be overwritten when the SDK is regenerated.*

# Table of Contents
- [**Overview**](#generated-javascript-readme)
- [**Accessing the connector**](#accessing-the-connector)
  - [*Connecting to the local Emulator*](#connecting-to-the-local-emulator)
- [**Queries**](#queries)
  - [*GetJournalEntriesByUser*](#getjournalentriesbyuser)
- [**Mutations**](#mutations)
  - [*CreateUser*](#createuser)
  - [*CreateJournalEntry*](#createjournalentry)
  - [*DeleteJournalEntry*](#deletejournalentry)

# Accessing the connector
A connector is a collection of Queries and Mutations. One SDK is generated for each connector - this SDK is generated for the connector `example`. You can find more information about connectors in the [Data Connect documentation](https://firebase.google.com/docs/data-connect#how-does).

You can use this generated SDK by importing from the package `@dataconnect/generated` as shown below. Both CommonJS and ESM imports are supported.

You can also follow the instructions from the [Data Connect documentation](https://firebase.google.com/docs/data-connect/web-sdk#set-client).

```typescript
import { getDataConnect } from 'firebase/data-connect';
import { connectorConfig } from '@dataconnect/generated';

const dataConnect = getDataConnect(connectorConfig);
```

## Connecting to the local Emulator
By default, the connector will connect to the production service.

To connect to the emulator, you can use the following code.
You can also follow the emulator instructions from the [Data Connect documentation](https://firebase.google.com/docs/data-connect/web-sdk#instrument-clients).

```typescript
import { connectDataConnectEmulator, getDataConnect } from 'firebase/data-connect';
import { connectorConfig } from '@dataconnect/generated';

const dataConnect = getDataConnect(connectorConfig);
connectDataConnectEmulator(dataConnect, 'localhost', 9399);
```

After it's initialized, you can call your Data Connect [queries](#queries) and [mutations](#mutations) from your generated SDK.

# Queries

There are two ways to execute a Data Connect Query using the generated Web SDK:
- Using a Query Reference function, which returns a `QueryRef`
  - The `QueryRef` can be used as an argument to `executeQuery()`, which will execute the Query and return a `QueryPromise`
- Using an action shortcut function, which returns a `QueryPromise`
  - Calling the action shortcut function will execute the Query and return a `QueryPromise`

The following is true for both the action shortcut function and the `QueryRef` function:
- The `QueryPromise` returned will resolve to the result of the Query once it has finished executing
- If the Query accepts arguments, both the action shortcut function and the `QueryRef` function accept a single argument: an object that contains all the required variables (and the optional variables) for the Query
- Both functions can be called with or without passing in a `DataConnect` instance as an argument. If no `DataConnect` argument is passed in, then the generated SDK will call `getDataConnect(connectorConfig)` behind the scenes for you.

Below are examples of how to use the `example` connector's generated functions to execute each query. You can also follow the examples from the [Data Connect documentation](https://firebase.google.com/docs/data-connect/web-sdk#using-queries).

## GetJournalEntriesByUser
You can execute the `GetJournalEntriesByUser` query using the following action shortcut function, or by calling `executeQuery()` after calling the following `QueryRef` function, both of which are defined in [dataconnect-generated/index.d.ts](./index.d.ts):
```typescript
getJournalEntriesByUser(vars: GetJournalEntriesByUserVariables): QueryPromise<GetJournalEntriesByUserData, GetJournalEntriesByUserVariables>;

interface GetJournalEntriesByUserRef {
  ...
  /* Allow users to create refs without passing in DataConnect */
  (vars: GetJournalEntriesByUserVariables): QueryRef<GetJournalEntriesByUserData, GetJournalEntriesByUserVariables>;
}
export const getJournalEntriesByUserRef: GetJournalEntriesByUserRef;
```
You can also pass in a `DataConnect` instance to the action shortcut function or `QueryRef` function.
```typescript
getJournalEntriesByUser(dc: DataConnect, vars: GetJournalEntriesByUserVariables): QueryPromise<GetJournalEntriesByUserData, GetJournalEntriesByUserVariables>;

interface GetJournalEntriesByUserRef {
  ...
  (dc: DataConnect, vars: GetJournalEntriesByUserVariables): QueryRef<GetJournalEntriesByUserData, GetJournalEntriesByUserVariables>;
}
export const getJournalEntriesByUserRef: GetJournalEntriesByUserRef;
```

If you need the name of the operation without creating a ref, you can retrieve the operation name by calling the `operationName` property on the getJournalEntriesByUserRef:
```typescript
const name = getJournalEntriesByUserRef.operationName;
console.log(name);
```

### Variables
The `GetJournalEntriesByUser` query requires an argument of type `GetJournalEntriesByUserVariables`, which is defined in [dataconnect-generated/index.d.ts](./index.d.ts). It has the following fields:

```typescript
export interface GetJournalEntriesByUserVariables {
  userId: UUIDString;
}
```
### Return Type
Recall that executing the `GetJournalEntriesByUser` query returns a `QueryPromise` that resolves to an object with a `data` property.

The `data` property is an object of type `GetJournalEntriesByUserData`, which is defined in [dataconnect-generated/index.d.ts](./index.d.ts). It has the following fields:
```typescript
export interface GetJournalEntriesByUserData {
  journalEntries: ({
    id: UUIDString;
    title?: string | null;
    content: string;
    createdAt: TimestampString;
    updatedAt: TimestampString;
  } & JournalEntry_Key)[];
}
```
### Using `GetJournalEntriesByUser`'s action shortcut function

```typescript
import { getDataConnect } from 'firebase/data-connect';
import { connectorConfig, getJournalEntriesByUser, GetJournalEntriesByUserVariables } from '@dataconnect/generated';

// The `GetJournalEntriesByUser` query requires an argument of type `GetJournalEntriesByUserVariables`:
const getJournalEntriesByUserVars: GetJournalEntriesByUserVariables = {
  userId: ..., 
};

// Call the `getJournalEntriesByUser()` function to execute the query.
// You can use the `await` keyword to wait for the promise to resolve.
const { data } = await getJournalEntriesByUser(getJournalEntriesByUserVars);
// Variables can be defined inline as well.
const { data } = await getJournalEntriesByUser({ userId: ..., });

// You can also pass in a `DataConnect` instance to the action shortcut function.
const dataConnect = getDataConnect(connectorConfig);
const { data } = await getJournalEntriesByUser(dataConnect, getJournalEntriesByUserVars);

console.log(data.journalEntries);

// Or, you can use the `Promise` API.
getJournalEntriesByUser(getJournalEntriesByUserVars).then((response) => {
  const data = response.data;
  console.log(data.journalEntries);
});
```

### Using `GetJournalEntriesByUser`'s `QueryRef` function

```typescript
import { getDataConnect, executeQuery } from 'firebase/data-connect';
import { connectorConfig, getJournalEntriesByUserRef, GetJournalEntriesByUserVariables } from '@dataconnect/generated';

// The `GetJournalEntriesByUser` query requires an argument of type `GetJournalEntriesByUserVariables`:
const getJournalEntriesByUserVars: GetJournalEntriesByUserVariables = {
  userId: ..., 
};

// Call the `getJournalEntriesByUserRef()` function to get a reference to the query.
const ref = getJournalEntriesByUserRef(getJournalEntriesByUserVars);
// Variables can be defined inline as well.
const ref = getJournalEntriesByUserRef({ userId: ..., });

// You can also pass in a `DataConnect` instance to the `QueryRef` function.
const dataConnect = getDataConnect(connectorConfig);
const ref = getJournalEntriesByUserRef(dataConnect, getJournalEntriesByUserVars);

// Call `executeQuery()` on the reference to execute the query.
// You can use the `await` keyword to wait for the promise to resolve.
const { data } = await executeQuery(ref);

console.log(data.journalEntries);

// Or, you can use the `Promise` API.
executeQuery(ref).then((response) => {
  const data = response.data;
  console.log(data.journalEntries);
});
```

# Mutations

There are two ways to execute a Data Connect Mutation using the generated Web SDK:
- Using a Mutation Reference function, which returns a `MutationRef`
  - The `MutationRef` can be used as an argument to `executeMutation()`, which will execute the Mutation and return a `MutationPromise`
- Using an action shortcut function, which returns a `MutationPromise`
  - Calling the action shortcut function will execute the Mutation and return a `MutationPromise`

The following is true for both the action shortcut function and the `MutationRef` function:
- The `MutationPromise` returned will resolve to the result of the Mutation once it has finished executing
- If the Mutation accepts arguments, both the action shortcut function and the `MutationRef` function accept a single argument: an object that contains all the required variables (and the optional variables) for the Mutation
- Both functions can be called with or without passing in a `DataConnect` instance as an argument. If no `DataConnect` argument is passed in, then the generated SDK will call `getDataConnect(connectorConfig)` behind the scenes for you.

Below are examples of how to use the `example` connector's generated functions to execute each mutation. You can also follow the examples from the [Data Connect documentation](https://firebase.google.com/docs/data-connect/web-sdk#using-mutations).

## CreateUser
You can execute the `CreateUser` mutation using the following action shortcut function, or by calling `executeMutation()` after calling the following `MutationRef` function, both of which are defined in [dataconnect-generated/index.d.ts](./index.d.ts):
```typescript
createUser(vars: CreateUserVariables): MutationPromise<CreateUserData, CreateUserVariables>;

interface CreateUserRef {
  ...
  /* Allow users to create refs without passing in DataConnect */
  (vars: CreateUserVariables): MutationRef<CreateUserData, CreateUserVariables>;
}
export const createUserRef: CreateUserRef;
```
You can also pass in a `DataConnect` instance to the action shortcut function or `MutationRef` function.
```typescript
createUser(dc: DataConnect, vars: CreateUserVariables): MutationPromise<CreateUserData, CreateUserVariables>;

interface CreateUserRef {
  ...
  (dc: DataConnect, vars: CreateUserVariables): MutationRef<CreateUserData, CreateUserVariables>;
}
export const createUserRef: CreateUserRef;
```

If you need the name of the operation without creating a ref, you can retrieve the operation name by calling the `operationName` property on the createUserRef:
```typescript
const name = createUserRef.operationName;
console.log(name);
```

### Variables
The `CreateUser` mutation requires an argument of type `CreateUserVariables`, which is defined in [dataconnect-generated/index.d.ts](./index.d.ts). It has the following fields:

```typescript
export interface CreateUserVariables {
  displayName: string;
  email?: string | null;
  photoUrl?: string | null;
}
```
### Return Type
Recall that executing the `CreateUser` mutation returns a `MutationPromise` that resolves to an object with a `data` property.

The `data` property is an object of type `CreateUserData`, which is defined in [dataconnect-generated/index.d.ts](./index.d.ts). It has the following fields:
```typescript
export interface CreateUserData {
  user_insert: User_Key;
}
```
### Using `CreateUser`'s action shortcut function

```typescript
import { getDataConnect } from 'firebase/data-connect';
import { connectorConfig, createUser, CreateUserVariables } from '@dataconnect/generated';

// The `CreateUser` mutation requires an argument of type `CreateUserVariables`:
const createUserVars: CreateUserVariables = {
  displayName: ..., 
  email: ..., // optional
  photoUrl: ..., // optional
};

// Call the `createUser()` function to execute the mutation.
// You can use the `await` keyword to wait for the promise to resolve.
const { data } = await createUser(createUserVars);
// Variables can be defined inline as well.
const { data } = await createUser({ displayName: ..., email: ..., photoUrl: ..., });

// You can also pass in a `DataConnect` instance to the action shortcut function.
const dataConnect = getDataConnect(connectorConfig);
const { data } = await createUser(dataConnect, createUserVars);

console.log(data.user_insert);

// Or, you can use the `Promise` API.
createUser(createUserVars).then((response) => {
  const data = response.data;
  console.log(data.user_insert);
});
```

### Using `CreateUser`'s `MutationRef` function

```typescript
import { getDataConnect, executeMutation } from 'firebase/data-connect';
import { connectorConfig, createUserRef, CreateUserVariables } from '@dataconnect/generated';

// The `CreateUser` mutation requires an argument of type `CreateUserVariables`:
const createUserVars: CreateUserVariables = {
  displayName: ..., 
  email: ..., // optional
  photoUrl: ..., // optional
};

// Call the `createUserRef()` function to get a reference to the mutation.
const ref = createUserRef(createUserVars);
// Variables can be defined inline as well.
const ref = createUserRef({ displayName: ..., email: ..., photoUrl: ..., });

// You can also pass in a `DataConnect` instance to the `MutationRef` function.
const dataConnect = getDataConnect(connectorConfig);
const ref = createUserRef(dataConnect, createUserVars);

// Call `executeMutation()` on the reference to execute the mutation.
// You can use the `await` keyword to wait for the promise to resolve.
const { data } = await executeMutation(ref);

console.log(data.user_insert);

// Or, you can use the `Promise` API.
executeMutation(ref).then((response) => {
  const data = response.data;
  console.log(data.user_insert);
});
```

## CreateJournalEntry
You can execute the `CreateJournalEntry` mutation using the following action shortcut function, or by calling `executeMutation()` after calling the following `MutationRef` function, both of which are defined in [dataconnect-generated/index.d.ts](./index.d.ts):
```typescript
createJournalEntry(vars: CreateJournalEntryVariables): MutationPromise<CreateJournalEntryData, CreateJournalEntryVariables>;

interface CreateJournalEntryRef {
  ...
  /* Allow users to create refs without passing in DataConnect */
  (vars: CreateJournalEntryVariables): MutationRef<CreateJournalEntryData, CreateJournalEntryVariables>;
}
export const createJournalEntryRef: CreateJournalEntryRef;
```
You can also pass in a `DataConnect` instance to the action shortcut function or `MutationRef` function.
```typescript
createJournalEntry(dc: DataConnect, vars: CreateJournalEntryVariables): MutationPromise<CreateJournalEntryData, CreateJournalEntryVariables>;

interface CreateJournalEntryRef {
  ...
  (dc: DataConnect, vars: CreateJournalEntryVariables): MutationRef<CreateJournalEntryData, CreateJournalEntryVariables>;
}
export const createJournalEntryRef: CreateJournalEntryRef;
```

If you need the name of the operation without creating a ref, you can retrieve the operation name by calling the `operationName` property on the createJournalEntryRef:
```typescript
const name = createJournalEntryRef.operationName;
console.log(name);
```

### Variables
The `CreateJournalEntry` mutation requires an argument of type `CreateJournalEntryVariables`, which is defined in [dataconnect-generated/index.d.ts](./index.d.ts). It has the following fields:

```typescript
export interface CreateJournalEntryVariables {
  userId: UUIDString;
  content: string;
  title?: string | null;
}
```
### Return Type
Recall that executing the `CreateJournalEntry` mutation returns a `MutationPromise` that resolves to an object with a `data` property.

The `data` property is an object of type `CreateJournalEntryData`, which is defined in [dataconnect-generated/index.d.ts](./index.d.ts). It has the following fields:
```typescript
export interface CreateJournalEntryData {
  journalEntry_insert: JournalEntry_Key;
}
```
### Using `CreateJournalEntry`'s action shortcut function

```typescript
import { getDataConnect } from 'firebase/data-connect';
import { connectorConfig, createJournalEntry, CreateJournalEntryVariables } from '@dataconnect/generated';

// The `CreateJournalEntry` mutation requires an argument of type `CreateJournalEntryVariables`:
const createJournalEntryVars: CreateJournalEntryVariables = {
  userId: ..., 
  content: ..., 
  title: ..., // optional
};

// Call the `createJournalEntry()` function to execute the mutation.
// You can use the `await` keyword to wait for the promise to resolve.
const { data } = await createJournalEntry(createJournalEntryVars);
// Variables can be defined inline as well.
const { data } = await createJournalEntry({ userId: ..., content: ..., title: ..., });

// You can also pass in a `DataConnect` instance to the action shortcut function.
const dataConnect = getDataConnect(connectorConfig);
const { data } = await createJournalEntry(dataConnect, createJournalEntryVars);

console.log(data.journalEntry_insert);

// Or, you can use the `Promise` API.
createJournalEntry(createJournalEntryVars).then((response) => {
  const data = response.data;
  console.log(data.journalEntry_insert);
});
```

### Using `CreateJournalEntry`'s `MutationRef` function

```typescript
import { getDataConnect, executeMutation } from 'firebase/data-connect';
import { connectorConfig, createJournalEntryRef, CreateJournalEntryVariables } from '@dataconnect/generated';

// The `CreateJournalEntry` mutation requires an argument of type `CreateJournalEntryVariables`:
const createJournalEntryVars: CreateJournalEntryVariables = {
  userId: ..., 
  content: ..., 
  title: ..., // optional
};

// Call the `createJournalEntryRef()` function to get a reference to the mutation.
const ref = createJournalEntryRef(createJournalEntryVars);
// Variables can be defined inline as well.
const ref = createJournalEntryRef({ userId: ..., content: ..., title: ..., });

// You can also pass in a `DataConnect` instance to the `MutationRef` function.
const dataConnect = getDataConnect(connectorConfig);
const ref = createJournalEntryRef(dataConnect, createJournalEntryVars);

// Call `executeMutation()` on the reference to execute the mutation.
// You can use the `await` keyword to wait for the promise to resolve.
const { data } = await executeMutation(ref);

console.log(data.journalEntry_insert);

// Or, you can use the `Promise` API.
executeMutation(ref).then((response) => {
  const data = response.data;
  console.log(data.journalEntry_insert);
});
```

## DeleteJournalEntry
You can execute the `DeleteJournalEntry` mutation using the following action shortcut function, or by calling `executeMutation()` after calling the following `MutationRef` function, both of which are defined in [dataconnect-generated/index.d.ts](./index.d.ts):
```typescript
deleteJournalEntry(vars: DeleteJournalEntryVariables): MutationPromise<DeleteJournalEntryData, DeleteJournalEntryVariables>;

interface DeleteJournalEntryRef {
  ...
  /* Allow users to create refs without passing in DataConnect */
  (vars: DeleteJournalEntryVariables): MutationRef<DeleteJournalEntryData, DeleteJournalEntryVariables>;
}
export const deleteJournalEntryRef: DeleteJournalEntryRef;
```
You can also pass in a `DataConnect` instance to the action shortcut function or `MutationRef` function.
```typescript
deleteJournalEntry(dc: DataConnect, vars: DeleteJournalEntryVariables): MutationPromise<DeleteJournalEntryData, DeleteJournalEntryVariables>;

interface DeleteJournalEntryRef {
  ...
  (dc: DataConnect, vars: DeleteJournalEntryVariables): MutationRef<DeleteJournalEntryData, DeleteJournalEntryVariables>;
}
export const deleteJournalEntryRef: DeleteJournalEntryRef;
```

If you need the name of the operation without creating a ref, you can retrieve the operation name by calling the `operationName` property on the deleteJournalEntryRef:
```typescript
const name = deleteJournalEntryRef.operationName;
console.log(name);
```

### Variables
The `DeleteJournalEntry` mutation requires an argument of type `DeleteJournalEntryVariables`, which is defined in [dataconnect-generated/index.d.ts](./index.d.ts). It has the following fields:

```typescript
export interface DeleteJournalEntryVariables {
  id: UUIDString;
}
```
### Return Type
Recall that executing the `DeleteJournalEntry` mutation returns a `MutationPromise` that resolves to an object with a `data` property.

The `data` property is an object of type `DeleteJournalEntryData`, which is defined in [dataconnect-generated/index.d.ts](./index.d.ts). It has the following fields:
```typescript
export interface DeleteJournalEntryData {
  journalEntry_delete?: JournalEntry_Key | null;
}
```
### Using `DeleteJournalEntry`'s action shortcut function

```typescript
import { getDataConnect } from 'firebase/data-connect';
import { connectorConfig, deleteJournalEntry, DeleteJournalEntryVariables } from '@dataconnect/generated';

// The `DeleteJournalEntry` mutation requires an argument of type `DeleteJournalEntryVariables`:
const deleteJournalEntryVars: DeleteJournalEntryVariables = {
  id: ..., 
};

// Call the `deleteJournalEntry()` function to execute the mutation.
// You can use the `await` keyword to wait for the promise to resolve.
const { data } = await deleteJournalEntry(deleteJournalEntryVars);
// Variables can be defined inline as well.
const { data } = await deleteJournalEntry({ id: ..., });

// You can also pass in a `DataConnect` instance to the action shortcut function.
const dataConnect = getDataConnect(connectorConfig);
const { data } = await deleteJournalEntry(dataConnect, deleteJournalEntryVars);

console.log(data.journalEntry_delete);

// Or, you can use the `Promise` API.
deleteJournalEntry(deleteJournalEntryVars).then((response) => {
  const data = response.data;
  console.log(data.journalEntry_delete);
});
```

### Using `DeleteJournalEntry`'s `MutationRef` function

```typescript
import { getDataConnect, executeMutation } from 'firebase/data-connect';
import { connectorConfig, deleteJournalEntryRef, DeleteJournalEntryVariables } from '@dataconnect/generated';

// The `DeleteJournalEntry` mutation requires an argument of type `DeleteJournalEntryVariables`:
const deleteJournalEntryVars: DeleteJournalEntryVariables = {
  id: ..., 
};

// Call the `deleteJournalEntryRef()` function to get a reference to the mutation.
const ref = deleteJournalEntryRef(deleteJournalEntryVars);
// Variables can be defined inline as well.
const ref = deleteJournalEntryRef({ id: ..., });

// You can also pass in a `DataConnect` instance to the `MutationRef` function.
const dataConnect = getDataConnect(connectorConfig);
const ref = deleteJournalEntryRef(dataConnect, deleteJournalEntryVars);

// Call `executeMutation()` on the reference to execute the mutation.
// You can use the `await` keyword to wait for the promise to resolve.
const { data } = await executeMutation(ref);

console.log(data.journalEntry_delete);

// Or, you can use the `Promise` API.
executeMutation(ref).then((response) => {
  const data = response.data;
  console.log(data.journalEntry_delete);
});
```

