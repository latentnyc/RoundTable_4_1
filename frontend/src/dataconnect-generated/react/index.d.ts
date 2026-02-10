import { CreateUserData, CreateUserVariables, GetJournalEntriesByUserData, GetJournalEntriesByUserVariables, CreateJournalEntryData, CreateJournalEntryVariables, DeleteJournalEntryData, DeleteJournalEntryVariables } from '../';
import { UseDataConnectQueryResult, useDataConnectQueryOptions, UseDataConnectMutationResult, useDataConnectMutationOptions} from '@tanstack-query-firebase/react/data-connect';
import { UseQueryResult, UseMutationResult} from '@tanstack/react-query';
import { DataConnect } from 'firebase/data-connect';
import { FirebaseError } from 'firebase/app';


export function useCreateUser(options?: useDataConnectMutationOptions<CreateUserData, FirebaseError, CreateUserVariables>): UseDataConnectMutationResult<CreateUserData, CreateUserVariables>;
export function useCreateUser(dc: DataConnect, options?: useDataConnectMutationOptions<CreateUserData, FirebaseError, CreateUserVariables>): UseDataConnectMutationResult<CreateUserData, CreateUserVariables>;

export function useGetJournalEntriesByUser(vars: GetJournalEntriesByUserVariables, options?: useDataConnectQueryOptions<GetJournalEntriesByUserData>): UseDataConnectQueryResult<GetJournalEntriesByUserData, GetJournalEntriesByUserVariables>;
export function useGetJournalEntriesByUser(dc: DataConnect, vars: GetJournalEntriesByUserVariables, options?: useDataConnectQueryOptions<GetJournalEntriesByUserData>): UseDataConnectQueryResult<GetJournalEntriesByUserData, GetJournalEntriesByUserVariables>;

export function useCreateJournalEntry(options?: useDataConnectMutationOptions<CreateJournalEntryData, FirebaseError, CreateJournalEntryVariables>): UseDataConnectMutationResult<CreateJournalEntryData, CreateJournalEntryVariables>;
export function useCreateJournalEntry(dc: DataConnect, options?: useDataConnectMutationOptions<CreateJournalEntryData, FirebaseError, CreateJournalEntryVariables>): UseDataConnectMutationResult<CreateJournalEntryData, CreateJournalEntryVariables>;

export function useDeleteJournalEntry(options?: useDataConnectMutationOptions<DeleteJournalEntryData, FirebaseError, DeleteJournalEntryVariables>): UseDataConnectMutationResult<DeleteJournalEntryData, DeleteJournalEntryVariables>;
export function useDeleteJournalEntry(dc: DataConnect, options?: useDataConnectMutationOptions<DeleteJournalEntryData, FirebaseError, DeleteJournalEntryVariables>): UseDataConnectMutationResult<DeleteJournalEntryData, DeleteJournalEntryVariables>;
