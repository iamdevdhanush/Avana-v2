import * as React from 'react'
import {
  MessageSquare, ThumbsUp, MapPin, Shield, ChevronDown,
  Send, Loader2, Filter, CheckCircle,
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { useUIStore } from '@/store/uiStore'
import { communityApi } from '@/services/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { formatRelativeTime, cn } from '@/lib/utils'
import type { CommunityPost, Comment } from '@/types'

type SortOption = 'newest' | 'upvoted' | 'nearby'
type PostFilter = 'all' | 'incidents' | 'discussions'

export function CommunityScreen() {
  const { user } = useAuthStore()
  const { addToast } = useUIStore()
  const [posts, setPosts] = React.useState<CommunityPost[]>([])
  const [loading, setLoading] = React.useState(true)
  const [page, setPage] = React.useState(1)
  const [hasMore, setHasMore] = React.useState(true)
  const [sortBy, setSortBy] = React.useState<SortOption>('newest')
  const [filter, setFilter] = React.useState<PostFilter>('all')
  const [showNewPost, setShowNewPost] = React.useState(false)
  const [newPostTitle, setNewPostTitle] = React.useState('')
  const [newPostContent, setNewPostContent] = React.useState('')
  const [submitting, setSubmitting] = React.useState(false)
  const [expandedPost, setExpandedPost] = React.useState<string | null>(null)
  const [comments, setComments] = React.useState<Record<string, Comment[]>>({})
  const [commentText, setCommentText] = React.useState('')
  const [commentLoading, setCommentLoading] = React.useState<string | null>(null)
  const [sortOpen, setSortOpen] = React.useState(false)

  const observerRef = React.useRef<IntersectionObserver | null>(null)
  const loadMoreRef = React.useRef<HTMLDivElement>(null)

  const fetchPosts = React.useCallback(async (pageNum: number, append = false) => {
    try {
      const response = await communityApi.getPosts({ page: pageNum, limit: 10 })
      const newPosts = response.data
      setPosts((prev) => append ? [...prev, ...newPosts] : newPosts)
      setHasMore(newPosts.length === 10)
    } catch {
      addToast({ title: 'Failed to load posts', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [addToast])

  React.useEffect(() => {
    setLoading(true)
    fetchPosts(1)
  }, [fetchPosts, sortBy, filter])

  React.useEffect(() => {
    if (!loadMoreRef.current) return
    observerRef.current = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && hasMore && !loading) {
        const nextPage = page + 1
        setPage(nextPage)
        fetchPosts(nextPage, true)
      }
    })
    observerRef.current.observe(loadMoreRef.current)
    return () => observerRef.current?.disconnect()
  }, [hasMore, loading, page, fetchPosts])

  const handleCreatePost = async () => {
    if (!newPostContent.trim()) return
    setSubmitting(true)
    try {
      await communityApi.createPost({
        content: newPostContent,
        post_type: 'general_discussion',
        latitude: null,
        longitude: null,
        location_name: null,
      })
      setNewPostTitle('')
      setNewPostContent('')
      setShowNewPost(false)
      addToast({ title: 'Post created', variant: 'success' })
      fetchPosts(1)
    } catch {
      addToast({ title: 'Failed to create post', variant: 'destructive' })
    } finally {
      setSubmitting(false)
    }
  }

  const handleToggleComments = async (postId: string) => {
    if (expandedPost === postId) {
      setExpandedPost(null)
      return
    }
    setExpandedPost(postId)
    if (!comments[postId]) {
      try {
        const data = await communityApi.getComments(postId)
        setComments((prev) => ({ ...prev, [postId]: data }))
      } catch {
        setComments((prev) => ({ ...prev, [postId]: [] }))
      }
    }
  }

  const handleAddComment = async (postId: string) => {
    if (!commentText.trim()) return
    setCommentLoading(postId)
    try {
      const newComment = await communityApi.createComment(postId, commentText)
      setComments((prev) => ({
        ...prev,
        [postId]: [...(prev[postId] || []), newComment],
      }))
      setCommentText('')
    } catch {
      addToast({ title: 'Failed to add comment', variant: 'destructive' })
    } finally {
      setCommentLoading(null)
    }
  }

  const filteredPosts = React.useMemo(() => {
    let result = [...posts]
    if (filter === 'incidents') result = result.filter((p) => p.isIncident)
    else if (filter === 'discussions') result = result.filter((p) => !p.isIncident)

    if (sortBy === 'upvoted') result.sort((a, b) => b.upvotes - a.upvotes)
    return result
  }, [posts, sortBy, filter])

  const sortOptions: { value: SortOption; label: string }[] = [
    { value: 'newest', label: 'Newest' },
    { value: 'upvoted', label: 'Most Upvoted' },
    { value: 'nearby', label: 'Near Me' },
  ]

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6 pb-20 lg:pb-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Community</h1>
        <Button size="sm" onClick={() => setShowNewPost(!showNewPost)}>
          {showNewPost ? 'Cancel' : 'New Post'}
        </Button>
      </div>

      {showNewPost && (
        <Card>
          <CardContent className="p-4 space-y-3">
            <Input
              placeholder="Post title"
              value={newPostTitle}
              onChange={(e) => setNewPostTitle(e.target.value)}
            />
            <Textarea
              placeholder="Share something with the community..."
              value={newPostContent}
              onChange={(e) => setNewPostContent(e.target.value)}
              className="min-h-[100px]"
            />
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setShowNewPost(false)}>Cancel</Button>
              <Button size="sm" onClick={handleCreatePost} disabled={submitting || !newPostTitle.trim() || !newPostContent.trim()}>
                {submitting && <Loader2 className="h-3 w-3 animate-spin mr-1" />}
                Post
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="flex items-center gap-2">
        {(['all', 'incidents', 'discussions'] as PostFilter[]).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              'rounded-full px-3 py-1 text-xs font-medium transition-colors',
              filter === f ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:bg-accent'
            )}
          >
            {f === 'all' ? 'All' : f === 'incidents' ? 'Incidents' : 'Discussions'}
          </button>
        ))}

        <div className="relative ml-auto">
          <button
            onClick={() => setSortOpen(!sortOpen)}
            className="flex items-center gap-1 rounded-md border border-input px-2.5 py-1 text-xs"
          >
            <Filter className="h-3 w-3" />
            {sortOptions.find((o) => o.value === sortBy)?.label}
            <ChevronDown className="h-3 w-3" />
          </button>
          {sortOpen && (
            <div className="absolute right-0 top-full mt-1 w-36 rounded-md border border-border bg-popover p-1 shadow-lg z-10">
              {sortOptions.map((o) => (
                <button
                  key={o.value}
                  onClick={() => { setSortBy(o.value); setSortOpen(false) }}
                  className={cn(
                    'w-full rounded-sm px-2 py-1.5 text-xs text-left hover:bg-accent',
                    sortBy === o.value && 'text-primary'
                  )}
                >
                  {o.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="space-y-3">
        {loading ? (
          Array.from({ length: 5 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="p-4 space-y-3">
                <div className="flex items-center gap-3">
                  <Skeleton className="h-8 w-8 rounded-full" />
                  <div className="space-y-1">
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-3 w-16" />
                  </div>
                </div>
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
              </CardContent>
            </Card>
          ))
        ) : filteredPosts.length === 0 ? (
          <Card>
            <CardContent className="p-8 text-center text-sm text-muted-foreground">
              No posts yet. Be the first to share!
            </CardContent>
          </Card>
        ) : (
          filteredPosts.map((post) => (
            <Card key={post.id}>
              <CardContent className="p-4 space-y-3">
                <div className="flex items-center gap-3">
                  <Avatar className="h-8 w-8">
                    <AvatarFallback>
                      {post.userName?.split(' ').map((n) => n[0]).join('').toUpperCase() || 'U'}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <p className="text-sm font-medium">{post.userName}</p>
                      {post.isVerified && (
                        <CheckCircle className="h-3.5 w-3.5 text-[#22C55E] shrink-0" fill="currentColor" style={{ opacity: 0.8 }} />
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">{post.createdAt ? new Date(post.createdAt).toLocaleString() : ''}</p>
                  </div>
                  {post.isIncident && (
                    <Badge variant="warning" className="ml-auto text-[10px]">Incident</Badge>
                  )}
                </div>

                <div>
                  <h3 className="font-semibold mb-1">{post.title}</h3>
                  <p className="text-sm text-muted-foreground">{post.content}</p>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  {post.tags?.map((tag) => (
                    <Badge key={tag} variant="secondary" className="text-[10px]">#{tag}</Badge>
                  ))}
                  {post.location?.address && (
                    <span className="flex items-center gap-1 text-xs text-muted-foreground">
                      <MapPin className="h-3 w-3" /> {post.location.address}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <button
                    className="flex items-center gap-1 hover:text-foreground transition-colors"
                    onClick={async () => {
                      try {
                        const result = await communityApi.vote(post.id, 'up')
                        setPosts(prev => prev.map(p => p.id === post.id
                          ? { ...p, upvotes: result.upvotes }
                          : p
                        ))
                      } catch { /* ignore */ }
                    }}
                  >
                    <ThumbsUp className="h-3.5 w-3.5" />
                    {post.upvotes}
                  </button>
                  <button
                    onClick={() => handleToggleComments(post.id)}
                    className="flex items-center gap-1 hover:text-foreground transition-colors"
                  >
                    <MessageSquare className="h-3.5 w-3.5" />
                    {post.commentCount || comments[post.id]?.length || 0}
                  </button>
                </div>

                {expandedPost === post.id && (
                  <div className="space-y-3 pt-2 border-t border-border">
                    <Separator />
                    {comments[post.id]?.map((comment) => (
                      <div key={comment.id} className="flex gap-2 text-sm">
                        <Avatar className="h-6 w-6">
                          <AvatarFallback className="text-[10px]">
                            {comment.userName?.split(' ').map((n) => n[0]).join('').toUpperCase() || 'U'}
                          </AvatarFallback>
                        </Avatar>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-medium">{comment.userName}</span>
                            <span className="text-[10px] text-muted-foreground">{formatRelativeTime(comment.createdAt)}</span>
                          </div>
                          <p className="text-xs text-muted-foreground">{comment.content}</p>
                        </div>
                      </div>
                    ))}
                    {(!comments[post.id] || comments[post.id].length === 0) && (
                      <p className="text-xs text-muted-foreground">No comments yet</p>
                    )}
                    <div className="flex gap-2">
                      <Input
                        placeholder="Write a comment..."
                        value={commentText}
                        onChange={(e) => setCommentText(e.target.value)}
                        className="h-8 text-xs"
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault()
                            handleAddComment(post.id)
                          }
                        }}
                      />
                      <Button
                        size="icon"
                        className="h-8 w-8 shrink-0"
                        onClick={() => handleAddComment(post.id)}
                        disabled={commentLoading === post.id || !commentText.trim()}
                      >
                        {commentLoading === post.id ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <Send className="h-3 w-3" />
                        )}
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ))
        )}

        <div ref={loadMoreRef} className="h-4" />
        {loading && (
          <div className="flex justify-center py-4">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        )}
      </div>
    </div>
  )
}
