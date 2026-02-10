import { ConnectorConfig, DataConnect, QueryRef, QueryPromise, MutationRef, MutationPromise } from 'firebase/data-connect';

export const connectorConfig: ConnectorConfig;

export type TimestampString = string;
export type UUIDString = string;
export type Int64String = string;
export type DateString = string;




export interface CreateJournalEntryData {
  journalEntry_insert: JournalEntry_Key;
}

export interface CreateJournalEntryVariables {
  userId: UUIDString;
  content: string;
  title?: string | null;
}

export interface CreateUserData {
  user_insert: User_Key;
}

export interface CreateUserVariables {
  displayName: string;
  email?: string | null;
  photoUrl?: string | null;
}

export interface DeleteJournalEntryData {
  journalEntry_delete?: JournalEntry_Key | null;
}

export interface DeleteJournalEntryVariables {
  id: UUIDString;
}

export interface EntryTag_Key {
  journalEntryId: UUIDString;
  tagId: UUIDString;
  __typename?: 'EntryTag_Key';
}

export interface GetJournalEntriesByUserData {
  journalEntries: ({
    id: UUIDString;
    title?: string | null;
    content: string;
    createdAt: TimestampString;
    updatedAt: TimestampString;
  } & JournalEntry_Key)[];
}

export interface GetJournalEntriesByUserVariables {
  userId: UUIDString;
}

export interface JournalEntry_Key {
  id: UUIDString;
  __typename?: 'JournalEntry_Key';
}

export interface Prompt_Key {
  id: UUIDString;
  __typename?: 'Prompt_Key';
}

export interface Tag_Key {
  id: UUIDString;
  __typename?: 'Tag_Key';
}

export interface User_Key {
  id: UUIDString;
  __typename?: 'User_Key';
}

interface CreateUserRef {
  /* Allow users to create refs without passing in DataConnect */
  (vars: CreateUserVariables): MutationRef<CreateUserData, CreateUserVariables>;
  /* Allow users to pass in custom DataConnect instances */
  (dc: DataConnect, vars: CreateUserVariables): MutationRef<CreateUserData, CreateUserVariables>;
  operationName: string;
}
export const createUserRef: CreateUserRef;

export function createUser(vars: CreateUserVariables): MutationPromise<CreateUserData, CreateUserVariables>;
export function createUser(dc: DataConnect, vars: CreateUserVariables): MutationPromise<CreateUserData, CreateUserVariables>;

interface GetJournalEntriesByUserRef {
  /* Allow users to create refs without passing in DataConnect */
  (vars: GetJournalEntriesByUserVariables): QueryRef<GetJournalEntriesByUserData, GetJournalEntriesByUserVariables>;
  /* Allow users to pass in custom DataConnect instances */
  (dc: DataConnect, vars: GetJournalEntriesByUserVariables): QueryRef<GetJournalEntriesByUserData, GetJournalEntriesByUserVariables>;
  operationName: string;
}
export const getJournalEntriesByUserRef: GetJournalEntriesByUserRef;

export function getJournalEntriesByUser(vars: GetJournalEntriesByUserVariables): QueryPromise<GetJournalEntriesByUserData, GetJournalEntriesByUserVariables>;
export function getJournalEntriesByUser(dc: DataConnect, vars: GetJournalEntriesByUserVariables): QueryPromise<GetJournalEntriesByUserData, GetJournalEntriesByUserVariables>;

interface CreateJournalEntryRef {
  /* Allow users to create refs without passing in DataConnect */
  (vars: CreateJournalEntryVariables): MutationRef<CreateJournalEntryData, CreateJournalEntryVariables>;
  /* Allow users to pass in custom DataConnect instances */
  (dc: DataConnect, vars: CreateJournalEntryVariables): MutationRef<CreateJournalEntryData, CreateJournalEntryVariables>;
  operationName: string;
}
export const createJournalEntryRef: CreateJournalEntryRef;

export function createJournalEntry(vars: CreateJournalEntryVariables): MutationPromise<CreateJournalEntryData, CreateJournalEntryVariables>;
export function createJournalEntry(dc: DataConnect, vars: CreateJournalEntryVariables): MutationPromise<CreateJournalEntryData, CreateJournalEntryVariables>;

interface DeleteJournalEntryRef {
  /* Allow users to create refs without passing in DataConnect */
  (vars: DeleteJournalEntryVariables): MutationRef<DeleteJournalEntryData, DeleteJournalEntryVariables>;
  /* Allow users to pass in custom DataConnect instances */
  (dc: DataConnect, vars: DeleteJournalEntryVariables): MutationRef<DeleteJournalEntryData, DeleteJournalEntryVariables>;
  operationName: string;
}
export const deleteJournalEntryRef: DeleteJournalEntryRef;

export function deleteJournalEntry(vars: DeleteJournalEntryVariables): MutationPromise<DeleteJournalEntryData, DeleteJournalEntryVariables>;
export function deleteJournalEntry(dc: DataConnect, vars: DeleteJournalEntryVariables): MutationPromise<DeleteJournalEntryData, DeleteJournalEntryVariables>;

